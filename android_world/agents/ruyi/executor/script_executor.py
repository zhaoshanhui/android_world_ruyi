import sys
import os
import subprocess
import tempfile
from datetime import datetime
import select
import time
import re

# 根据操作系统选择不同的模块
if os.name == 'posix':
    import fcntl
else:
    import msvcrt

class ScriptExecutor:
    """
    This module is used to execute scripts using RuyiAgent.
    """
    def __init__(self):
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        # 跨平台日志路径设置
        if os.name == 'nt':  # Windows 系统
            self.log_file = os.path.join(os.path.expanduser('~'), 'Documents', 'ruyi_agent.log')
        else:  # macOS/Linux 系统
            self.log_file = os.path.join(os.path.expanduser('~'), 'Desktop', 'ruyi_agent.log')
        
        self.execute_process = None
        self.task_end = False
        self.task_success = False
        self.log_queue = None  # 新增 log_queue 属性
        self.log_buffer = ""  # 新增日志缓冲区（需在任何日志调用前初始化）
        self.current_temp_file = None  # 追踪当前临时文件路径
        self.execution_error = None  # 用于存储执行错误信息

        # 初始化时仅清理较久之前残留的临时文件，避免并行任务互相影响
        self.cleanup_all_temp_files(older_than_seconds=3600)  # 仅清理 1h 之前残留的临时文件

        # 定义模板字符串
        self.template_content = '''# -*- coding: utf-8 -*-
import sys
import os

# 添加 RuyiAgent 的 Python 路径
sys.path.append("{ruyi_agent_path}")

from ruyi.agent import RuyiAgent
from ruyi.task import RuyiTask
from ruyi.config import RuyiConfig, RuyiArgParser

class DynamicTask(RuyiTask):
    def __init__(self):
        super().__init__()
        self.task_id = "android_world_task"
        self.description = """{task_description}
"""
        self.code_script_labeled = """{code_script_labeled}
"""
        self.NL_script_labeled = """{NL_script_labeled}
"""


    def main(self, agent):
        device_manager, data, fm, user = agent.device_manager, agent.data, agent.fm, agent.user
{script_content}

if __name__ == '__main__':
    yaml_file = os.path.join("{ruyi_agent_path}", 'config.yaml')
    parser = RuyiArgParser((RuyiConfig,))
    config = parser.parse_yaml_file(yaml_file=yaml_file)[0]
    agent = RuyiAgent(config)
    task = DynamicTask()
    agent.task.execute_task(task)
'''
        # self.log_buffer 已在构造前部初始化

    def set_log_queue(self, log_queue):
        """设置 log_queue"""
        self.log_queue = log_queue

    def cleanup_temp_file(self):
        """清理当前临时文件"""
        if self.current_temp_file and os.path.exists(self.current_temp_file):
            try:
                os.remove(self.current_temp_file)
                # self._log(f"已清理临时文件: {self.current_temp_file}")
            except Exception as e:
                self._log(self.format_ruyi_log(f"清理临时文件失败: {str(e)}"))
            finally:
                self.current_temp_file = None

    def cleanup_all_temp_files(self, older_than_seconds: int = 0):
        """清理可能残留的临时文件。
        仅清理早于 older_than_seconds 的旧文件，防止并行任务误删彼此正在使用的临时文件。
        """
        try:
            # 使用系统临时目录
            temp_dir = tempfile.gettempdir()
            if not os.path.exists(temp_dir):
                return
            
            # 清理所有匹配模式的临时文件
            import glob
            pattern = os.path.join(temp_dir, "ruyi_script_*.ruyi")
            temp_files = glob.glob(pattern)
            
            cleaned_count = 0
            for temp_file in temp_files:
                try:
                    # 仅删除足够旧的文件
                    if older_than_seconds > 0:
                        try:
                            mtime = os.path.getmtime(temp_file)
                            if (time.time() - mtime) < older_than_seconds:
                                continue
                        except Exception:
                            # 获取时间失败时跳过删除，避免误删
                            continue
                    os.remove(temp_file)
                    cleaned_count += 1
                    self._log(self.format_ruyi_log(f"已清理残留临时文件: {temp_file}"))
                except Exception as e:
                    self._log(self.format_ruyi_log(f"清理残留临时文件失败 {temp_file}: {str(e)}"))
            
            if cleaned_count > 0:
                self._log(self.format_ruyi_log(f"总共清理了 {cleaned_count} 个残留临时文件"))
                
        except Exception as e:
            self._log(self.format_ruyi_log(f"清理残留临时文件时出错: {str(e)}"))

    def stop_execution(self):
        """停止当前执行并清理资源"""
        # 停止执行进程
        if self.execute_process:
            try:
                self.execute_process.terminate()  # 先尝试优雅终止
                # 等待一小段时间看进程是否结束
                try:
                    self.execute_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.execute_process.kill()  # 如果没有结束则强制杀死
                self._log(self.format_ruyi_log("执行进程已停止"))
            except Exception as e:
                self._log(self.format_ruyi_log(f"停止执行进程时出错: {str(e)}"))
            finally:
                self.execute_process = None
        
        # 清理当前临时文件
        self.cleanup_temp_file()
        
        # 避免并行任务互相影响，不在这里全量清理所有临时文件
        
        # 重置任务状态
        self.task_end = True
        self.task_success = False

    def _log(self, message, is_error=False):
        """跨平台日志写入"""
        # 去除ANSI转义字符
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        message = ansi_escape.sub('', message)
        
        log_message = message
        if not isinstance(log_message, str):
            log_message = str(log_message)
        
        # 将日志同时写入缓冲区（防御性初始化，避免极端情况下属性未就绪）
        try:
            if not hasattr(self, 'log_buffer') or self.log_buffer is None:
                self.log_buffer = ''
            self.log_buffer += log_message
        except Exception:
            # 保障不因日志失败影响主流程
            pass

        # 如果 log_queue 存在，将日志写入队列
        if self.log_queue:
            try:
                self.log_queue.put(log_message)
            except Exception:
                pass

    def format_ruyi_log(self, message: str, level: str = "info") -> str:
        """
        为非 RuyiAgent 的日志添加与 RuyiAgent 相同的前缀。
        形如: 'YYYY-MM-DD HH:MM:SS [info  ] message'
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        level_formatted = level.lower().ljust(9)
        return f"{timestamp} [{level_formatted}  ] {message}"

    def get_log(self):
        """获取当前日志内容并清空缓冲区"""
        log_content = self.log_buffer
        self.log_buffer = ""  # 清空缓冲区
        return log_content

    def check_task_end(self, log_content):
        """
            检查任务是否结束
            TODO: 需要改版，现在这个版本太老了，Ruyi Agent 可能已经不输出 "finish task" 了
                  不能简单得根据日志内容来判断任务的结束
        """
        # 增加对 "Handled error" 的判断，避免将已处理的错误误判为任务失败
        # if ("error" in log_content.lower() and "handled error" not in log_content.lower()) and "runtime error" not in log_content.lower() or "任务执行出错" in log_content:
        #     self.task_success = False
        #     return True
        if "finish task" in log_content:
            self.task_success = True
            return True
        else:
            return False

    def check_execution_error(self, log_content):
        """检查输出中是否存在Python执行错误"""
        # 对常见网络错误进行特殊处理：不视为任务结束
        network_error_signals = (
            "HTTPSConnectionPool",
            "ConnectTimeout",
            "ConnectTimeoutError",
            "MaxRetryError",
        )
        if any(sig in log_content for sig in network_error_signals):
            return False
        
        # 检查常见 Python 错误模式, 如 SyntaxError, IndentationError 等
        error_pattern = r'(\w+Error): (.*)'
        match = re.search(error_pattern, log_content)
        if match:
            error_type = match.group(1)
            error_message = match.group(2)
            self.execution_error = {
                'type': error_type,
                'message': error_message,
                'full_log': log_content
            }
            return True
        return False

    # 生成任务内容
    def generate_task_content(self, scripts, code_script_labeled, NL_script_labeled, task="task", variables=None, device_mappings=None):
        # 获取 RuyiAgent 路径（修复路径分隔符问题）
        ruyi_agent_path = os.path.join(os.path.dirname(self.current_dir), 'RuyiAgent')

        # 将路径转换为原始字符串格式
        ruyi_agent_path = os.path.normpath(ruyi_agent_path).replace('\\', '/')  # 统一使用正斜杠

        # 准备脚本内容（添加适当的缩进）
        formatted_scripts = '\n'.join(f'        {line}' for line in scripts.splitlines())

        # 准备变量映射与设备映射的字符串表示（Python 字面量；None 回退为空字典）
        variable_mapping_str = repr(variables if variables is not None else {})
        device_mappings_str = repr(device_mappings if device_mappings is not None else {})

        # 为了避免在模板中使用三重双引号导致字符串提前结束，对内容中的 \"\"\" 进行转义
        escaped_code_script_labeled = code_script_labeled.replace('"""', '\\\"\\\"\\\"') if code_script_labeled is not None else ""
        escaped_NL_script_labeled = NL_script_labeled.replace('"""', '\\\"\\\"\\\"') if NL_script_labeled is not None else ""

        # 对 task 中的双引号进行转义
        escaped_task = task.replace('"', '\\"') if isinstance(task, str) else str(task)

        task_content = self.template_content.format(
            ruyi_agent_path=ruyi_agent_path.replace('\\', r'\\'),  # 双重转义反斜杠
            task_description=escaped_task,
            code_script_labeled=escaped_code_script_labeled,
            NL_script_labeled=escaped_NL_script_labeled,
            script_content=formatted_scripts,
            variable_mapping=variable_mapping_str,
            device_mappings=device_mappings_str
        )
        return task_content

    # 创建临时 .ruyi 文件
    def create_temp_ruyi_script(self, task_content: str, track_current: bool = True) -> str:
        try:
            # 使用系统临时目录
            temp_dir = tempfile.gettempdir()

            # 生成带时间戳的文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 精确到毫秒
            script_filename = f"ruyi_script_{timestamp}.ruyi"
            temp_path = os.path.join(temp_dir, script_filename)

            # 记录当前临时文件路径或只创建一次性文件
            if track_current:
                self.current_temp_file = temp_path

            # 创建 .ruyi 脚本文件
            with open(temp_path, 'w', encoding='utf-8') as script_file:
                script_file.write(task_content)

            return temp_path
        except Exception as e:
            self._log(self.format_ruyi_log(f"创建脚本文件失败: {str(e)}"), is_error=True)
            raise

    # 检查编译错误（仅语法层面，不执行）
    def check_compile_errors(self, scripts, code_script_labeled, NL_script_labeled, task="task", variables=None, device_mappings=None):
        """
        生成与执行时相同的 .ruyi 脚本文件，并进行语法编译检查。
        返回: (compiled_ok: bool, error: dict | None)
        """
        temp_path = None
        try:
            task_content = self.generate_task_content(scripts, code_script_labeled, NL_script_labeled, task, variables, device_mappings)
            # 对于编译检查，不跟踪为 current_temp_file，避免影响正在执行的任务
            temp_path = self.create_temp_ruyi_script(task_content, track_current=False)

            # 使用内置 compile 对源码进行语法检查（不会执行 import）
            try:
                compile(task_content, temp_path, 'exec')
                return True, None
            except SyntaxError as e:
                error_info = {
                    'type': e.__class__.__name__,
                    'message': e.msg,
                    'lineno': e.lineno,
                    'offset': e.offset,
                    'text': e.text
                }
                return False, error_info
            except Exception as e:
                error_info = {
                    'type': e.__class__.__name__,
                    'message': str(e)
                }
                return False, error_info
        finally:
            # 编译检查用的临时文件立即清理
            try:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

    # 执行脚本
    def execute_scripts(self, scripts, code_script_labeled="", NL_script_labeled="", task="task", variables=None, device_mappings=None):
        self.log_buffer = ""  # 每次执行前清空缓冲区
        self.task_end = False
        self.task_success = False
        self.execution_error = None  # 重置错误信息

        # 停止之前的执行并清理资源
        self.stop_execution()

        self._log(self.format_ruyi_log("="*42))
        self._log(self.format_ruyi_log("开始新的任务执行"))
        # 对 task 中的双引号进行转义
        escaped_task = task.replace('"', '\\"')
        self._log(self.format_ruyi_log(f"任务名称: {escaped_task}"))
        # self._log(f"脚本内容:\n{scripts}")
        
        try:
            # 生成任务内容
            task_content = self.generate_task_content(scripts, code_script_labeled, NL_script_labeled, task, variables, device_mappings)

            # 将执行的 Ruyi Script 保存到桌面 / 保存到本地，用于调试
            current_time = datetime.now()
            # task_content_path = os.path.join(os.path.expanduser('~'), 'Desktop', f'task_content_{current_time.strftime("%Y%m%d_%H%M%S_%f")}.ruyi')
            
            task_file_name = task if isinstance(task, str) else str(task)
            if len(task_file_name) > 30:
                task_file_name = task_file_name[:30]  # 控制文件名前缀长度，避免过长
                
            task_content_path = os.path.join('ruyi_scripts', f'{task_file_name}_{current_time.strftime("%Y%m%d_%H%M%S_%f")}.ruyi')
            with open(task_content_path, "w", encoding="utf-8") as f:
                f.write(task_content)
            
            # 创建执行脚本文件
            try:
                temp_path = self.create_temp_ruyi_script(task_content, track_current=True)
            except Exception as e:
                self._log(self.format_ruyi_log(f"创建脚本文件失败: {str(e)}"), is_error=True)
                raise
            
            try:
                # self._log(f"执行脚本文件: {temp_path}")
                # 获取项目目录作为工作目录，用于配置读取、写入文件时的相对路径地址
                project_dir = "./"

                # 执行脚本文件并实时获取输出
                # 注意：不再使用 start_new_session=True，将子进程保留在与当前进程相同的进程组中。
                # 这样当用户在终端中通过 Ctrl+C 终止 `run.py` 时，操作系统发送的 SIGINT
                # 会同时传递给该子进程，避免脚本在后台“孤儿进程”式继续运行。
                self.execute_process = subprocess.Popen(
                    [sys.executable, "-u", temp_path],  # unbuffered 模式
                    cwd=project_dir,  # 设置工作目录为项目目录，用于配置读取、写入文件时的相对路径地址
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",  # 指定编码为 utf-8
                    bufsize=1,
                    universal_newlines=True,
                    env={**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8'},  # 添加环境变量
                    # start_new_session=True
                )
                # self._log(f"启动执行脚本文件进程: {self.execute_process.pid}")

                if os.name == 'posix':
                    # Unix/Linux 系统：设置非阻塞读取
                    for fd in [self.execute_process.stdout, self.execute_process.stderr]:
                        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                else:
                    # Windows 系统：使用线程读取输出
                    import threading, queue
                    stdout_queue = queue.Queue()
                    stderr_queue = queue.Queue()
                    
                    def enqueue_output(pipe, output_queue):
                        for line in iter(pipe.readline, ''):
                            output_queue.put(line)
                        pipe.close()
                    
                    threading.Thread(target=enqueue_output, args=(self.execute_process.stdout, stdout_queue), daemon=True).start()
                    threading.Thread(target=enqueue_output, args=(self.execute_process.stderr, stderr_queue), daemon=True).start()
                
                stop_reading = False
                while not stop_reading:
                    if os.name == 'nt':
                        # Windows 平台：从线程队列中获取输出
                        while not stdout_queue.empty():
                            line = stdout_queue.get()
                            print(line, end='', flush=True)
                            self._log(line.strip())
                            # 检查语法错误
                            # if self.check_execution_error(line):
                            #     self.task_end = True
                            #     stop_reading = True
                            #     break
                            # if self.check_task_end(line):
                            #     self.task_end = True
                            #     stop_reading = True
                            #     break
                        while not stderr_queue.empty():
                            line = stderr_queue.get()
                            print(line, end='', file=sys.stderr, flush=True)
                            self._log(line.strip(), is_error=True)
                            # 检查语法错误
                            # if self.check_execution_error(line):
                            #     self.task_end = True
                            #     stop_reading = True
                            #     break
                            # if self.check_task_end(line):
                            #     self.task_end = True
                            #     stop_reading = True
                            #     break
                    else:
                        # macOS/Linux 平台：继续使用非阻塞读取
                        output = ''
                        try:
                            chunk = self.execute_process.stdout.read()
                            if chunk:
                                output = chunk.decode('utf-8', errors='replace') if isinstance(chunk, bytes) else str(chunk)
                                print(output, end='')
                                self._log(output.strip())
                                # 检查语法错误
                                # if self.check_execution_error(output):
                                #     # self._log(self.format_ruyi_log("=====在读取 stdout 时，检测到错误，结束任务 log 读取=====", level="debug"), is_error=True)
                                #     # self._log(self.format_ruyi_log(f"{output}", level="debug"), is_error=True)
                                #     # self._log(self.format_ruyi_log("="*60, level="debug"), is_error=True)
                                #     self.task_end = True
                                #     stop_reading = True
                                # elif self.check_task_end(output):
                                #     # self._log(self.format_ruyi_log("=====在读取 stdout 时，检测到任务结束，结束任务 log 读取=====", level="debug"), is_error=True)
                                #     # self._log(self.format_ruyi_log(f"{output}", level="debug"), is_error=True)
                                #     # self._log(self.format_ruyi_log("="*60, level="debug"), is_error=True)
                                #     self.task_end = True
                                #     stop_reading = True
                        except Exception as _:
                            pass

                        # 读取错误输出
                        error = ''
                        try:
                            err_chunk = self.execute_process.stderr.read()
                            if err_chunk:
                                error = err_chunk.decode('utf-8', errors='replace') if isinstance(err_chunk, bytes) else str(err_chunk)
                                print(error, end='', file=sys.stderr)
                                self._log(error.strip(), is_error=True)
                                # 检查语法错误
                                # if self.check_execution_error(error):
                                #     # self._log(self.format_ruyi_log("=====在读取 stderr 时，检测到错误，结束任务 log 读取====="), is_error=True)
                                #     # self._log(self.format_ruyi_log(f"{error}"), is_error=True)
                                #     # self._log(self.format_ruyi_log("="*60), is_error=True)
                                #     self.task_end = True
                                #     stop_reading = True
                        except Exception as _:
                            pass
                    
                    # 检查进程是否结束
                    if self.execute_process.poll() is not None:
                        break

                    # 适当降低CPU占用
                    time.sleep(0.1)

                success = self.task_success
                # self._log(f"任务执行结束，执行结果：{'成功' if success else '失败'}")
                return success, self.execution_error  # 返回执行结果和语法错误信息
                
            except Exception as e:
                self._log(self.format_ruyi_log(f"执行脚本时发生错误: {str(e)}"), is_error=True)
                raise
            
        except Exception as e:
            self._log(self.format_ruyi_log(f"发生未预期的错误: {str(e)}"), is_error=True)
            raise
            
        finally:
            # 清理临时文件
            self.cleanup_temp_file()
            self._log(self.format_ruyi_log("任务执行结束"))
            self._log(self.format_ruyi_log("="*42))  # 添加结束分隔符


if __name__ == '__main__':
    scripts = "device.start_app('Contacts')\nui.root.locate_view('Create Contact').click()"
    executor = ScriptExecutor()
    success, execution_error = executor.execute_scripts(scripts, task="Create Contact")
    print(f"ScriptsExecutor 任务执行{'成功' if success else '失败'}")
    if execution_error:
        print(f"执行错误: {execution_error['message']}")

