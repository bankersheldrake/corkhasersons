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

    for entry in entries:
        if entry in exclude_list:
            continue
        path = directory + entry
        if os.path.isdir(path):
            if output_format == 'text':
                print(prefix + "+-- " + entry)
                print_tree(path, file_flag, prefix + "    ", level)
            elif output_format == 'chat':
                print(prefix + "|-- " + entry)
                print_tree(path, file_flag, prefix + "|   ", level, output_format)
            elif output_format == 'json':
                print_tree(path, file_flag, "", level, output_format, json_dict[base_name]["folders"])
        elif file_flag and re.match(pattern, entry):
            if output_format in ['text', 'chat']:
                print(prefix + "|-- " + entry)
            elif output_format == 'json':
                json_dict[base_name]["files"].append(entry)

    # remove the "folders" key if there are no subfolders
    if output_format == 'json' and not json_dict[base_name].get("folders"):
        del json_dict[base_name]["folders"]

    # remove the "files" key if there are no files or if -f was not passed
    if output_format == 'json' and (not file_flag or not json_dict[base_name].get("files")):
        json_dict[base_name].pop("files", None)

    return json_dict


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Print directory tree structure.")
    parser.add_argument("-p", "--path", help="Path of the directory", default=".")
    parser.add_argument("-d", "--depth", help="Depth of the tree", type=int, default=-1)
    parser.add_argument("-f", "--files", help="Include files", action="store_true")
    parser.add_argument("-r", "--regex", help="Regex pattern to match file/folder names", default=".*")
    parser.add_argument("-e", "--exclude", help="Names of files/folders to exclude", nargs='+', default=[])
    parser.add_argument("-o", "--output", help="Output format", choices=['text', 'json', 'chat'], default='text')
    args = parser.parse_args()

    path = args.path
    depth = args.depth
    files_flag = args.files
    pattern = args.regex
    exclude_list = args.exclude
    output_format = args.output
    base_name = os.path.basename(path)

    if output_format == 'json':
        tree_dict = print_tree(path, files_flag, "", depth, output_format, {})
        print(json.dumps(tree_dict, indent=4))
    else:
        print(base_name)
        print_tree(path, files_flag, "", depth, output_format)
