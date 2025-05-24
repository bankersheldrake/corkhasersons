#!/usr/bin/env python3

import sys
import json
import base64
import requests
import os
import shutil

def encode_image_to_base64(image_path):
    try:
        print(f"Encoding image at: {image_path}")
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    except Exception as e:
        print(f"Error while encoding image: {e}")
        sys.exit(1)

def create_payload(base64_image):
    print("Creating OpenAI API payload...")
    return {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                      "type": "text",
                      "text": "Extract the grid of data from this image. The grid is an 8x6 table showing flight departure and return dates, with corresponding cost in points. Some date combinations have a waitlist flag, this must also be tracked. Some combinations have no flight availability, in which case the value should be null.\nThe output must be strictly in JSON format with the following structure: { \"depart date\": { \"return date\": { \"points\": number, \"waitlist\": boolean } } }\nReturn only the JSON object. Do not include any explanations, text, preambles, or formatting like backticks. Ensure the output is a valid, directly parsable JSON object."
                    },
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]
            }
        ],
        "temperature": 0,
        "max_tokens": 2048
    }

def send_request(api_key, payload):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    try:
        print("Sending request to OpenAI API...")
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        print(f"Response received with status code: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.text}")
            sys.exit(1)
        return response.json()
    except Exception as e:
        print(f"Error while making API request: {e}")
        sys.exit(1)

def process_images(folder_path, api_key):
    temp_folder = os.path.join(folder_path, "temp")
    archive_folder = os.path.join(folder_path, "Archive")

    # Create temp and archive folders if they don't exist
    os.makedirs(temp_folder, exist_ok=True)
    os.makedirs(archive_folder, exist_ok=True)

    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)

        # Process only PNG files
        if file_name.lower().endswith(".png") and os.path.isfile(file_path):
            print(f"Processing file: {file_name}")

            # Move to temp folder
            temp_path = os.path.join(temp_folder, file_name)
            shutil.move(file_path, temp_path)

            try:
                # Encode image and send to API
                base64_image = encode_image_to_base64(temp_path)
                payload = create_payload(base64_image)
                response = send_request(api_key, payload)

                # Save output JSON in the source folder with matching name
                output_file = os.path.join(folder_path, os.path.splitext(file_name)[0] + ".json")
                with open(output_file, "w") as f:
                    json.dump(response, f, indent=4)
                print(f"Output saved to: {output_file}")

                # Move image to Archive folder
                archive_path = os.path.join(archive_folder, file_name)
                shutil.move(temp_path, archive_path)
                print(f"Moved {file_name} to Archive folder.\n")

            except Exception as e:
                print(f"Error processing {file_name}: {e}")
                # Move file back to source folder in case of failure
                shutil.move(temp_path, file_path)

def main():
    try:
        print("Parsing input arguments...")
        tArgs = json.loads(sys.argv[1])

        # Extract and validate arguments
        folder_path = tArgs.get("folder_path")
        api_key = tArgs.get("OPENAI_API_KEY")

        if not api_key:
            raise ValueError("Missing API key (OPENAI_API_KEY).")
        if not folder_path or not os.path.isdir(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        print(f"Processing images in folder: {folder_path}")
        process_images(folder_path, api_key)
        print("All images processed successfully!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
