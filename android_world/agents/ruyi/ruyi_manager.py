from .planner import ScriptGenerator
from .executor import ScriptExecutor


class RuyiManager:
    def __init__(self):
        self.script_generator = ScriptGenerator()
        self.script_executor = ScriptExecutor()

    def execute_task(self, task_description: str):
        print("=" * 10, "Executing task with Ruyi", "=" * 10)
        print("=" * 10, "Task description:", task_description, "=" * 10)

        print("=" * 10, "Generating workflow...", "=" * 10)
        workflow = self.script_generator.generate_workflow(task_description)

        # 对生成的 workflow 进行按行打标签，形成 labeled_workflow
        labeled_workflow = _label_workflow(workflow)

        print("=" * 10, "Transferring workflow to code...", "=" * 10)
        labeled_python_script = self.script_generator.transfer_workflow_to_code(task_description, labeled_workflow)

        # 将带标签的 workflow 一并传给执行器，方便后续使用
        self.script_executor.execute_scripts(labeled_python_script, code_script_labeled = labeled_python_script, NL_script_labeled=labeled_workflow, task=task_description)
        return


def _label_workflow(workflow: str) -> str:
    """
    为 Ruyi DSL 工作流的每一行添加前缀标签：
    - 标签从 1 开始递增，形如 "[1]"、"[2]"……
    - 空行和仅包含注释的行不添加标签
    - 每一行中只会添加一个标签（如果行首已经有形如 "[n]" 的标签，则不再重复添加）
    """
    if not workflow:
        return workflow

    labeled_lines = []
    label_counter = 1

    for line in workflow.splitlines():
        original_line = line
        stripped = line.lstrip()

        # 空行：直接保留
        if stripped == "":
            labeled_lines.append(original_line)
            continue

        # 仅包含注释的行（支持以 "#" 或 "//" 开头的注释）
        if stripped.startswith("#") or stripped.startswith("//"):
            labeled_lines.append(original_line)
            continue

        # 如果行首已经有形如 "[数字]" 的标签，则认为已经打过标签，防止重复
        if stripped.startswith("["):
            # 简单检查是否是 [number]
            closing_idx = stripped.find("]")
            if closing_idx > 1 and stripped[1:closing_idx].isdigit():
                labeled_lines.append(original_line)
                continue

        # 为该行添加新的标签前缀
        indent_len = len(line) - len(stripped)
        indent = line[:indent_len]
        labeled_line = f"{indent}[{label_counter}]{stripped}"
        labeled_lines.append(labeled_line)
        label_counter += 1

    return "\n".join(labeled_lines)

