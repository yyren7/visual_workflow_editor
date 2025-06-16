import subprocess
import os
from dotenv import load_dotenv # Import dotenv

load_dotenv() # Load variables from .env file

# Configuration - Load from environment variables
smb_host = os.getenv("SMB_HOST")
smb_share_flow = os.getenv("SMB_SHARE_LLM")
smb_share_config = os.getenv("SMB_SHARE_CONFIG")
smb_user_domain = os.getenv("SMB_USER_DOMAIN")
smb_username = os.getenv("SMB_USERNAME")
smb_password = os.getenv("SMB_PASSWORD")

# Check if all necessary environment variables are set
if not all([smb_host, smb_share_flow, smb_share_config, smb_user_domain, smb_username, smb_password]):
    print("Error: One or more SMB configuration environment variables are not set in the .env file.")
    print("Please ensure SMB_HOST, SMB_SHARE_LLM, SMB_SHARE_CONFIG, SMB_USER_DOMAIN, SMB_USERNAME, SMB_PASSWORD are all defined.")
    exit(1) # Exit if configuration is incomplete

local_download_dir = "/workspace/backend/langgraphchat/synced_files"
files_to_download = ["llm_test.zip"]

# Full SMB user credentials, format 'DOMAIN\\username%password'
# smb_credentials = f"{smb_user_domain}\\\\{smb_username}%{smb_password}" # Old method, commented out
smb_user_pass = f"{smb_username}%{smb_password}" # New method: username%password
smb_base_url = f"//{smb_host}/{smb_share_flow}"

def download_files():
    # Create local directory (if it doesn't exist)
    try:
        os.makedirs(local_download_dir, exist_ok=True)
        print(f"Local directory '{local_download_dir}' ensured to exist.")
    except OSError as e:
        print(f"Failed to create directory '{local_download_dir}': {e}")
        return

    for file_name in files_to_download:
        remote_file_path = file_name # File is located in the root of the share
        local_file_path = os.path.join(local_download_dir, file_name)
        
        # Build smbclient command
        # Example: smbclient '//172.30.84.220/llm_test' -U 'JP\\J100052060%frank123' \\
        #         -c 'get auto.py /workspace/backend/tests/share_folder/auto.py'
        smb_get_command = f"get {remote_file_path} {local_file_path}"
        # full_command = [ # Old command construction
        #     "smbclient",
        #     smb_base_url,
        #     "-U",
        #     smb_credentials,
        #     "-c",
        #     smb_get_command
        # ]
        full_command = [ # New command construction
            "smbclient",
            smb_base_url,
            "-W", # Specify workgroup/domain
            smb_user_domain,
            "-U", # Specify user and password
            smb_user_pass,
            "-c",
            smb_get_command
        ]
        
        print(f"Preparing to download '{file_name}' to '{local_file_path}'...")
        # For security, consider hiding or partially hiding the password when printing the command
        # print(f"Executing command: {' '.join(full_command)}") # Will contain password when actually executed

        try:
            # Using subprocess.run for simpler blocking execution and error handling
            result = subprocess.run(full_command, capture_output=True, text=True, timeout=60, check=False)

            if result.returncode == 0:
                print(f"Successfully downloaded '{file_name}'.")
                if result.stdout:
                    print(f"smbclient output:\n{result.stdout}")
                # smbclient often uses stderr for status messages even on success
                if result.stderr and "NT_STATUS_OK" not in result.stderr : # Heuristic to filter common success messages on stderr
                     print(f"smbclient (possible) messages/warnings:\n{result.stderr}")
            else:
                print(f"Failed to download '{file_name}'. Return code: {result.returncode}")
                if result.stdout:
                    print(f"smbclient standard output:\n{result.stdout}")
                if result.stderr:
                    print(f"smbclient error output:\n{result.stderr}")
        
        except subprocess.TimeoutExpired:
            print(f"Download of '{file_name}' timed out.")
        except FileNotFoundError:
            print("Error: 'smbclient' command not found. Please ensure it is installed and in your PATH.")
            break # Stop if smbclient is not found
        except Exception as e:
            print(f"An unknown error occurred while downloading '{file_name}': {e}")

# New: Function to upload files
def upload_file(local_file_path, remote_file_name):
    print(f"Preparing to upload '{local_file_path}' to '{remote_file_name}' in the shared directory...")

    if not os.path.exists(local_file_path):
        print(f"Error: Local file '{local_file_path}' does not exist, cannot upload.")
        return False # Added return

    # Build smbclient command
    # Example: smbclient '//172.30.84.220/llm_test' -W JP -U J100052060%frank123 \\
    #         -c 'put /workspace/backend/tests/conftest.py conftest.py'
    smb_put_command = f"put {local_file_path} {remote_file_name}"
    full_command = [
        "smbclient",
        smb_base_url,
        "-W", 
        smb_user_domain,
        "-U", 
        smb_user_pass,
        "-c",
        smb_put_command
    ]

    try:
        result = subprocess.run(full_command, capture_output=True, text=True, timeout=60, check=False)

        if result.returncode == 0:
            print(f"Successfully uploaded '{local_file_path}' as '{remote_file_name}'.")
            if result.stdout:
                print(f"smbclient output:\n{result.stdout}")
            if result.stderr and "NT_STATUS_OK" not in result.stderr:
                 print(f"smbclient (possible) messages/warnings:\n{result.stderr}")
            return True # Added return
        else:
            print(f"Failed to upload '{local_file_path}'. Return code: {result.returncode}")
            if result.stdout:
                print(f"smbclient standard output:\n{result.stdout}")
            if result.stderr:
                print(f"smbclient error output:\n{result.stderr}")
            return False # Added return
    
    except subprocess.TimeoutExpired:
        print(f"Upload of '{local_file_path}' timed out.")
        return False # Added return
    except FileNotFoundError:
        print("Error: 'smbclient' command not found. Please ensure it is installed and in your PATH.")
        return False # Added return
    except Exception as e:
        print(f"An unknown error occurred while uploading '{local_file_path}': {e}")
        return False # Added return

if __name__ == "__main__":
    print("Starting file download process...")
    download_files()
    print("File download process finished.")

    # Example usage for upload, ensure these variables are defined if you uncomment
    # local_file_to_upload = "/workspace/backend/tests/llm_sas_test/concatenated_output/concatenated_flow.xml"
    # remote_file_name_for_upload = "concatenated_flow.xml"
    # print("\nStarting file upload process...")
    # upload_file(local_file_to_upload, remote_file_name_for_upload)
    # print("File upload process finished.")

    # print("\nStarting batch file upload process...")
    # source_directory = "/workspace/backend/tests/llm_sas_test/specific_clamp_output"
    # if not os.path.isdir(source_directory):
    #     print(f"Error: Source directory '{source_directory}' does not exist or is not a directory.")
    # else:
    #     files_to_upload_in_dir = [f for f in os.listdir(source_directory) if os.path.isfile(os.path.join(source_directory, f))]
    #     if not files_to_upload_in_dir:
    #         print(f"No files found in directory '{source_directory}'.")
    #     else:
    #         successful_uploads = 0
    #         failed_uploads = 0
    #         for file_name in files_to_upload_in_dir:
    #             local_file_path = os.path.join(source_directory, file_name)
    #             remote_file_name = file_name # Use the same name for the remote file
    #             print(f"--- Attempting to upload: {file_name} ---")
    #             if upload_file(local_file_path, remote_file_name):
    #                 successful_uploads += 1
    #             else:
    #                 failed_uploads += 1
    #             print(f"--- Finished attempting to upload: {file_name} ---")
            
    #         print("\nBatch file upload process finished.")
    #         print(f"Summary: {successful_uploads} files uploaded successfully, {failed_uploads} files failed to upload.") 