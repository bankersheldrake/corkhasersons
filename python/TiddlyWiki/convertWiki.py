#!/usr/bin/env python3

import sys,time
import json
import os
import requests
import subprocess
import urllib.parse


def read_instructions(instructions_file):
    """
    Reads the instructions from the given file.
    """
    try:
        print(f"Reading instructions from: {instructions_file}")
        with open(instructions_file, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Error reading instructions file: {e}")
        sys.exit(1)


def create_payload(file_content, instructions):
    """
    Creates the API payload using the instructions and file content.
    """
    print("Creating API payload...")
    return {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": f"{instructions}\n\nThe file content to convert is:\n\n{file_content}"
            }
        ],
        "temperature": 0,
        "max_tokens": 2048
    }


def send_request(api_key, payload, url):
    """
    Sends the payload to the specified API endpoint.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    try:
        print("Sending request to API...")
        response = requests.post(url, headers=headers, json=payload)
        print(f"Response received with status code: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return None
        return response.json()
    except Exception as e:
        print(f"Error while making API request: {e}")
        return None

import os
import time
import json
import re

def markdown_to_tiddlywiki(markdown_text):
    """
    Convert Markdown content to TiddlyWiki format.

    Args:
        markdown_text (str): Input Markdown content.

    Returns:
        str: Converted TiddlyWiki content.
    """
    tiddlywiki_text = markdown_text

    # Convert headings
    tiddlywiki_text = re.sub(r'^######\s*(.*)$', r'!!!!!! \1', tiddlywiki_text, flags=re.MULTILINE)
    tiddlywiki_text = re.sub(r'^#####\s*(.*)$', r'!!!!! \1', tiddlywiki_text, flags=re.MULTILINE)
    tiddlywiki_text = re.sub(r'^####\s*(.*)$', r'!!!! \1', tiddlywiki_text, flags=re.MULTILINE)
    tiddlywiki_text = re.sub(r'^###\s*(.*)$', r'!!! \1', tiddlywiki_text, flags=re.MULTILINE)
    tiddlywiki_text = re.sub(r'^##\s*(.*)$', r'!! \1', tiddlywiki_text, flags=re.MULTILINE)
    tiddlywiki_text = re.sub(r'^#\s*(.*)$', r'! \1', tiddlywiki_text, flags=re.MULTILINE)

    # Convert links [[Text|URL]]
    tiddlywiki_text = re.sub(r'\[\[(.*?)\|(.*?)\]\]', r'[[\1|\2]]', tiddlywiki_text)

    # Convert unordered lists
    tiddlywiki_text = re.sub(r'^\s*[-*]\s*(.*)$', r' * \1', tiddlywiki_text, flags=re.MULTILINE)

    # Convert inline code blocks to `<code>` tags
    # tiddlywiki_text = re.sub(r'`([^`]*)`', r'``\1``', tiddlywiki_text)
    return tiddlywiki_text

def extract_content(response, error_log_folder="errors"):
    """
    Extracts the 'choices' elements from the OpenAI API response.
    If an error occurs, writes the raw content to a file and logs the file name.
    """
    try:
        # Convert the response to a raw JSON string
        raw_content = json.dumps(response, indent=4)
        
        # Attempt to extract the 'content' field
        choices = response.get("choices", [])
        if not choices:
            raise ValueError("No 'choices' field found in the OpenAI response.")
        
        content_raw = choices[0].get("message", {}).get("content", "")
        if not content_raw:
            raise ValueError("Empty 'content' field in the first choice.")

        # Parse the content as JSON
        content_parsed = json.loads(content_raw)
        return content_parsed

    except Exception as e:
        print(f"Error extracting content: {e}")

        # Ensure the error log folder exists
        os.makedirs(error_log_folder, exist_ok=True)

        # Generate a unique file name for logging
        error_file = os.path.join(error_log_folder, f"error_{int(time.time())}.json")

        try:
            # Write the raw response to the error file
            with open(error_file, "w", encoding="utf-8") as f:
                f.write(raw_content)
            print(f"Raw response written to error file: {error_file}")
        except Exception as file_error:
            print(f"Failed to write error file: {file_error}")

        return None


def run_curl_command(data, base_url, tiddler_name):
    """
    Executes the curl command with the given data and dynamically constructed target URL.
    """
    try:
        # Construct the target URL with the tiddler name
        encoded_tiddler_name = urllib.parse.quote(tiddler_name)
        target_url = f"{base_url}/{encoded_tiddler_name}"
        print(f"Running curl command for target URL: {target_url}")

        command = [
            "curl",
            "-X", "PUT",
            "-H", "Content-Type: application/json",
            "-H", "X-Requested-With: TiddlyWiki",
            "--data-binary", json.dumps(data),
            target_url
        ]
        subprocess.run(command, check=True)
        print("Curl command executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error running curl command: {e}")
    except Exception as e:
        print(f"Unexpected error running curl command: {e}")


def process_md_files(folder_path, instructions_file, api_key, api_url, base_url, skip_files=0, limit_files=None):
    """
    Processes .md files with optional skipping and limiting.
    """
    instructions = read_instructions(instructions_file)
    files_processed = 0
    files_encountered = 0

    for root, _, files in os.walk(folder_path):
        for idx, file_name in enumerate(files):
            if not file_name.lower().endswith(".md"):
                continue

            files_encountered += 1
            print(f"Encountered file {files_encountered}: {file_name}")

            if files_encountered <= skip_files:
                print(f"Skipping file: {file_name}")
                continue

            if limit_files is not None and files_processed >= limit_files:
                print("Reached processing limit. Exiting.")
                return

            file_path = os.path.join(root, file_name)
            print(f"Processing file: {file_path}")

            try:
                # Read the content of the .md file
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()

                files_processed += 1

                # Create and send the payload
                payload = create_payload(file_content, instructions)
                response = send_request(api_key, payload, api_url)

                # Extract and send data using curl
                if response:
                    tiddler_name = os.path.splitext(file_name)[0]  # Use file name without extension as tiddler name
                    extracted_data = extract_content(response)

                    if extracted_data:
                        # Prepare the data dictionary
                        data = {
                            "title": tiddler_name,
                            "text": f"! Summary\n{extracted_data.get('summary', 'No summary available')}\n\n"
                                    f"{markdown_to_tiddlywiki(file_content)}",
                            "tags": extracted_data.get('tags', [])
                        }
                        run_curl_command(data, base_url, tiddler_name)

            except Exception as e:
                print(f"Error processing {file_path}: {e}")

    print(f"Total files processed: {files_processed}. Total files encountered: {files_encountered}.")

def main():
    try:
        print("Parsing input arguments...")
        tArgs = json.loads(sys.argv[1])

        # Extract and validate arguments
        folder_path = tArgs.get("folder_path")
        instructions_file = tArgs.get("instructions_file")
        api_key = tArgs.get("OPENAI_API_KEY")
        api_url = tArgs.get("API_URL")
        base_url = tArgs.get("base_url")
        skip_files = tArgs.get("skip_files", 0)
        limit_files = tArgs.get("limit_files")

        if not api_key:
            raise ValueError("Missing API key (OPENAI_API_KEY).")
        if not api_url:
            raise ValueError("Missing API URL (API_URL).")
        if not folder_path or not os.path.isdir(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        if not instructions_file or not os.path.isfile(instructions_file):
            raise FileNotFoundError(f"Instructions file not found: {instructions_file}")
        if not base_url:
            raise ValueError("Missing base URL (base_url).")

        print(f"Processing .md files in folder: {folder_path}")
        process_md_files(folder_path, instructions_file, api_key, api_url, base_url, skip_files, limit_files)
        print("All .md files processed successfully!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
