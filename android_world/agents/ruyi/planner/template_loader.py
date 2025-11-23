from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

TEMPLATE_JS_PATH = os.environ['TEMPLATE_JS_PATH']

TARGET_TEMPLATE_VARIABLES: List[str] = [
    "EnglishRuyiDSLSyntax",
    "EnglishRuyiDSLSyntaxExamples",
    "EnglishWorkflowToPythonHint",
    "EnglishRuyiPythonFrameworkIntroduction",
    "EnglishExamplesIntroduction",
    "EnglishExamples",
    "EnglishTaskNameExamplePrompt",
    "EnglishOutputNotes",
]


def _unescape_template_literal_char(char: str) -> str:
    escape_map = {
        "`": "`",
        "\\": "\\",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "$": "$",
        "'": "'",
        '"': '"',
    }
    return escape_map.get(char, char)


def _extract_template_literal(content: str, key: str) -> str:
    marker = f"{key}: `"
    start = content.find(marker)
    if start == -1:
        raise ValueError(f"Cannot find template literal for key '{key}'.")

    index = start + len(marker)
    chars: List[str] = []

    while index < len(content):
        char = content[index]
        if char == "`":
            return "".join(chars)

        if char == "\\":
            index += 1
            if index >= len(content):
                raise ValueError(f"Incomplete escape sequence in '{key}'.")
            chars.append(_unescape_template_literal_char(content[index]))
            index += 1
            continue

        chars.append(char)
        index += 1

    raise ValueError(f"Unterminated template literal for key '{key}'.")


def _load_template_variables() -> Dict[str, str]:
    template_js_path = Path(TEMPLATE_JS_PATH)
    if not template_js_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_js_path}")

    content = template_js_path.read_text(encoding="utf-8")
    data: Dict[str, str] = {}
    for key in TARGET_TEMPLATE_VARIABLES:
        data[key] = _extract_template_literal(content, key)
    return data


TEMPLATE_VARIABLES: Dict[str, str] = _load_template_variables()


if __name__ == "__main__":
    print(TEMPLATE_VARIABLES)
    
    with open("EnglishRuyiDSLSyntax.txt", "w", encoding="utf-8") as f:
        f.write(TEMPLATE_VARIABLES["EnglishRuyiDSLSyntax"])
    
    # import json
    # with open("english_template_variables.json", "w", encoding="utf-8") as f:
    #     json.dump(TEMPLATE_VARIABLES, f, indent=4)
    
    # print(TEMPLATE_VARIABLES["EnglishRuyiDSLSyntax"])
    # print(TEMPLATE_VARIABLES["EnglishRuyiDSLSyntaxExamples"])
    # print(TEMPLATE_VARIABLES["EnglishWorkflowToPythonHint"])
    # print(TEMPLATE_VARIABLES["EnglishRuyiPythonFrameworkIntroduction"])
    # print(TEMPLATE_VARIABLES["EnglishExamplesIntroduction"])
    # print(TEMPLATE_VARIABLES["EnglishExamples"])
    # print(TEMPLATE_VARIABLES["EnglishTaskNameExamplePrompt"])
    # print(TEMPLATE_VARIABLES["EnglishOutputNotes"])