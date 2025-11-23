# Copyright 2025 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""T3A: Text-only Autonomous Agent for Android."""

import json
import os
from datetime import datetime

from android_world.agents import agent_utils
from android_world.agents import base_agent
from android_world.agents import infer
from android_world.agents import m3a_utils
from android_world.env import adb_utils
from android_world.env import interface
from android_world.env import json_action
from android_world.env import representation_utils

from .ruyi import RuyiManager

class RuyiAgent(base_agent.EnvironmentInteractingAgent):
  """Ruyi Agent for Android."""

  def __init__(
      self,
      env: interface.AsyncEnv,
      name: str = 'RuyiAgent',
  ):
    """Initializes a RuyiAgent.

    Args:
      env: The environment.
      name: The agent name.
    """
    super().__init__(env, name)
    self.additional_guidelines = None

  def reset(self, go_home_on_reset: bool = False):
    super().reset(go_home_on_reset)
    self.env.hide_automation_ui()

  def set_task_guidelines(self, task_guidelines: list[str]) -> None:
    self.additional_guidelines = task_guidelines

  def step(self, goal: str) -> base_agent.AgentInteractionResult:
    """Performs a single interaction step.

    当前 RuyiAgent 只是一个简单占位实现：不对环境执行任何实际操作，
    而是直接将本次任务标记为“已完成”，并返回相应的结束标志。

    Args:
      goal: 当前任务的目标描述。

    Returns:
      AgentInteractionResult，其中:
        - done: True，表示本轮 episode 已经结束；
        - data: 本 step 的元信息，供上层记录与可视化使用。
    """
    print(f'RuyiAgent receives goal: "{goal}".')

    os.system("adb shell settings put secure show_ime_with_hard_keyboard 0")
    os.system("adb forward tcp:51825 tcp:6666")

    task_start = datetime.now()
    ruyi_manager = RuyiManager()
    ruyi_manager.execute_task(goal)
    task_end = datetime.now()

    self._record_execution(goal, task_start, task_end)

    step_data: dict[str, object] = {
        'before_screenshot': None,
        'after_screenshot': None,
        'before_element_list': None,
        'after_element_list': None,
        'action_prompt': None,
        'action_output': None,
        'action_raw_response': None,
        'summary_prompt': None,
        'summary': (
            'RuyiAgent: task marked as completed without performing UI actions. '
            f'Goal: "{goal}".'
        ),
        'summary_raw_response': None,
    }

    # 关键：通过 done=True 告诉上层 episode_runner，本次任务已经结束。
    return base_agent.AgentInteractionResult(
        done=True,
        data=step_data,
    )

  def _record_execution(
      self, goal: str, start_time: datetime, end_time: datetime
  ) -> None:
    """记录单次任务执行信息，便于后续审计与调试。"""
    record_path = 'ruyi_execution_records.json'
    duration_seconds = (end_time - start_time).total_seconds()
    record = {
        'goal': goal,
        'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
        'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
        'duration_seconds': round(duration_seconds, 2),
    }

    try:
      if os.path.exists(record_path):
        with open(record_path, 'r', encoding='utf-8') as record_file:
          data = json.load(record_file)
      else:
        data = []
    except (json.JSONDecodeError, OSError):
      data = []

    if not isinstance(data, list):
      data = []
    data.append(record)

    try:
      with open(record_path, 'w', encoding='utf-8') as record_file:
        json.dump(data, record_file, ensure_ascii=False, indent=4)
    except OSError as exc:
      print(f'记录任务执行信息失败: {exc}')