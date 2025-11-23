import re
from datetime import datetime

from .prompt_manager import PromptManager
from .models import LLM


class ScriptGenerator:
    def __init__(self):
        self.prompt_manager = PromptManager()
        self.llm = LLM("gpt-5-chat")

    def _extract_tag_content(self, text: str, tag: str) -> str | None:
        if not text:
            return None
        pattern = rf"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
        if match:
            match_content = match.group(1).strip()
            if match_content.startswith("```") and match_content.endswith("```"):
                match_content = match_content.splitlines()[1:-1]
                return "\n".join(match_content).strip()
            return match_content.strip()
        return None

    def generate_workflow(self, task_description: str):
        generate_workflow_prompt = self.prompt_manager.generate_workflow(task_description)

        # print("=" * 10, "Generating workflow prompt:", generate_workflow_prompt, "=" * 10)
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        with open(f"ruyi_scripts/generate_workflow_prompt_{current_time}.txt", "w") as f:
            f.write(generate_workflow_prompt)

        response = self.llm.query(generate_workflow_prompt)
        thought = self._extract_tag_content(response, "thought")
        workflow = self._extract_tag_content(response, "workflow")

        with open(f"ruyi_scripts/generate_workflow_response_{current_time}.txt", "w") as f:
            f.write(response)
        
        if thought is None:
            print("Warning: <thought> tag missing in workflow response.")
        if workflow is None:
            print("Warning: <workflow> tag missing in workflow response.")
            return response
        return workflow

    def transfer_workflow_to_code(self, task_description: str, workflow: str):
        transfer_workflow_to_code_prompt = self.prompt_manager.transfer_workflow_to_code(task_description, workflow)

        # print("=" * 10, "Transferring workflow to code prompt:", transfer_workflow_to_code_prompt, "=" * 10)
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        with open(f"ruyi_scripts/transfer_workflow_to_code_prompt_{current_time}.txt", "w") as f:
            f.write(transfer_workflow_to_code_prompt)

        response = self.llm.query(transfer_workflow_to_code_prompt)
        thought = self._extract_tag_content(response, "thought")
        python_script = self._extract_tag_content(response, "labeled_python_script")

        with open(f"ruyi_scripts/transfer_workflow_to_code_response_{current_time}.txt", "w") as f:
            f.write(response)
        
        if thought is None:
            print("Warning: <thought> tag missing in python script response.")
        if python_script is None:
            print("Warning: <python_script> tag missing in python script response.")
            return response
        return python_script