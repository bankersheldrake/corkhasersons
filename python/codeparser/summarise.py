import argparse
import ast
import json
import os
import re
import tokenize
from io import BytesIO
from typing import List, Dict

import subprocess
import json

def extract_object_info(node):
    object_info = {
        'name': '',
        'docstring': '',
        'parameters': []
    }

    if isinstance(node, ast.ClassDef):
        object_info['name'] = node.name
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Str):
            object_info['docstring'] = node.body[0].value.s
        for subnode in node.body:
            if isinstance(subnode, ast.FunctionDef):
                param_info = {
                    'name': subnode.name,
                    'docstring': '',
                    'parameters': []
                }
                if subnode.body and isinstance(subnode.body[0], ast.Expr) and isinstance(subnode.body[0].value, ast.Str):
                    param_info['docstring'] = subnode.body[0].value.s
                for arg in subnode.args.args:
                    param_info['parameters'].append(arg.arg)
                object_info['parameters'].append(param_info)
    elif isinstance(node, ast.FunctionDef):
        object_info['name'] = node.name
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Str):
            object_info['docstring'] = node.body[0].value.s
        for arg in node.args.args:
            object_info['parameters'].append(arg.arg)

    return object_info


def parse_python(filename: str) -> List[Dict[str, any]]:
    object_infos = []

    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()

    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            object_info = extract_object_info(node)
            object_infos.append(object_info)

    return object_infos




def parse_typescript(filename: str) -> List[Dict[str, any]]:
    result = subprocess.run(['node', 'parse_typescript.js', filename], capture_output=True)
    
    # Check for errors
    if result.returncode != 0:
        raise Exception("Error running the TypeScript parser script. Make sure Node.js and the script are correctly set up.")
        
    # Parse the output from the Node.js script
    object_infos = json.loads(result.stdout)
    
    return object_infos


def parse_file(filename: str) -> List[Dict[str, any]]:
    _, file_extension = os.path.splitext(filename)

    if file_extension == '.py':
        return parse_python(filename)
    elif file_extension == '.ts':
        return parse_typescript(filename)
    else:
        raise ValueError(f'Unsupported file type: {file_extension}')


def generate_documentation(filename: str):
    object_infos = parse_file(filename)

    json_output = json.dumps(object_infos, indent=2)

    with open('documentation.json', 'w', encoding='utf-8') as f:
        f.write(json_output)

    print('Documentation generated and saved as documentation.json.')


def main():
    parser = argparse.ArgumentParser(description='Parse source file and generate object documentation.')
    parser.add_argument('filename', help='Path to the source file')
    args = parser.parse_args()

    generate_documentation(args.filename)


if __name__ == '__main__':
    main()
