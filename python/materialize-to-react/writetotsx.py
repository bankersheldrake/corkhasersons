import subprocess
import tempfile
import os
import argparse
import sys

def execute_command(command):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, error = process.communicate()
    return output.decode('utf-8'), error.decode('utf-8'), process.returncode

def get_script_directory():
    return os.path.dirname(os.path.abspath(__file__))

def get_existing_content(output_file):
    if os.path.isfile(output_file):
        with open(output_file, 'r') as file:
            return file.read()
    return ""

def find_start_end_indices(content, start_tag, end_tag):
    start_index = content.find(start_tag)
    end_index = content.rfind(end_tag)
    if start_index != -1 and end_index != -1:
        end_index = end_index + len(end_tag)
    return start_index, end_index

def execute_command_line_tool(script_path, input_file, output_file):
    command = f'{sys.executable} {script_path} -i {input_file} -o {output_file}'
    # print(command)
    output, error, return_code = execute_command(command)
    if return_code != 0:
        print(f'Error occurred while executing the command:\n{error}\n{output}')
        sys.exit(1)
    # print(output, error, return_code)

def read_sub_output(output_file):
    with open(output_file, 'r') as file:
        return file.read()

def write_final_content(output_file, content):
    with open(output_file, 'w') as file:
        file.write(content)

def main(input_file, output_file):
    try:
        script_dir = get_script_directory()
        start_tag = '{/* REPLACEME START */}'
        end_tag = '{/* REPLACEME END */}'

        existing_content = get_existing_content(output_file)
        start_index, end_index = find_start_end_indices(existing_content, start_tag, end_tag)

        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            output_filename = temp_file.name
        # print(os.path.join(script_dir, 'materialize-to-react.py'))
        execute_command_line_tool(os.path.join(script_dir, 'materialize-to-react.py'), input_file, output_filename)

        sub_output_content = read_sub_output(output_filename)
        output_content = existing_content[:start_index] + f'{start_tag}\n{sub_output_content}\n{end_tag}' + existing_content[end_index:]

        write_final_content(output_file, output_content)

        os.remove(output_filename)

        print('Process completed successfully.')

    except Exception as e:
        print(f'An error occurred: {str(e)}')
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Path to the input HTML file.')
    parser.add_argument('-o', '--output', help='Name of the output file.')
    args = parser.parse_args()

    if not args.input or not args.output:
        parser.print_help()
        sys.exit(1)

    main(args.input, args.output)
