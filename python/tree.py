import os
import argparse
import re
import json

def print_tree(directory, file_flag, prefix="", level=-1, output_format='text', json_dict={}):
    if level == 0:
        return

    if directory[-1] != os.sep:
        directory += os.sep

    base_name = os.path.basename(directory[:-1])
    if output_format == 'json':
        json_dict[base_name] = {"folders": {}}
        if file_flag:
            json_dict[base_name]["files"] = []

    if level != -1:
        level -= 1

    try:
        entries = sorted(os.listdir(directory))
    except OSError as e:
        print(f"{prefix}Error reading directory {directory}: {str(e)}")
        return

    # Separate directories and files
    dir_entries = [entry for entry in entries if os.path.isdir(directory + entry)]
    file_entries = [entry for entry in entries if os.path.isfile(directory + entry)]

    for entry in dir_entries:
        path = directory + entry
        relative_path = os.path.relpath(path, start=base_path)
        # (print(inc) for inc in include_list)
        if any(re.search(inc, relative_path) for inc in include_list) or not include_list:
            if entry in exclude_list:
                continue
            if output_format == 'text':
                print(prefix + "+-- " + entry)
                print_tree(path, file_flag, prefix + "    ", level)
            elif output_format == 'chat':
                print(prefix + "|-- " + entry)
                print_tree(path, file_flag, prefix + "|   ", level, output_format)
            elif output_format == 'json':
                print_tree(path, file_flag, "", level, output_format, json_dict[base_name]["folders"])

    for entry in file_entries:
        path = directory + entry
        relative_path = os.path.relpath(path, start=base_path)
        if any(re.search(inc, relative_path) for inc in include_list) or not include_list:
            if entry in exclude_list:
                continue
            if file_flag and re.match(pattern, entry):
                if output_format in ['text', 'chat']:
                    print(prefix + "|-- " + entry)
                elif output_format == 'json':
                    json_dict[base_name]["files"].append(entry)

    if output_format == 'json':
        if not json_dict[base_name].get("folders"):
            del json_dict[base_name]["folders"]
        if not file_flag or not json_dict[base_name].get("files"):
            json_dict[base_name].pop("files", None)

    return json_dict


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print directory tree structure.")
    parser.add_argument("-p", "--path", help="Path of the directory", default=".")
    parser.add_argument("-d", "--depth", help="Depth of the tree", type=int, default=-1)
    parser.add_argument("-f", "--files", help="Include files", action="store_true")
    parser.add_argument("-r", "--regex", help="Regex pattern to match file/folder names", default=".*")
    parser.add_argument("-e", "--exclude", help="Names of files/folders to exclude (space delimited strings)", nargs='+', default=[])
    parser.add_argument("-i", "--include", help="Regex patterns for paths to include (space delimited strings)", nargs='+', default=[])
    parser.add_argument("-o", "--output", help="Output format", choices=['text', 'json', 'chat'], default='text')
    args = parser.parse_args()

    base_path = os.path.abspath(args.path)
    base_name = os.path.basename(base_path)
    depth = args.depth
    files_flag = args.files
    pattern = args.regex
    exclude_list = args.exclude
    include_list = args.include
    output_format = args.output

    if output_format == 'json':
        tree_dict = print_tree(base_path, files_flag, "", depth, output_format, {})
        print(json.dumps(tree_dict, indent=4))
    else:
        print(base_name)
        print_tree(base_path, files_flag, "", depth, output_format)
