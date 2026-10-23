import requests
import json
import os
import shutil
import sys

BASE_URL = "http://localhost:8000"
USERNAME = "superuser"
PASSWORD = "superuser"

def testimages():
    print("\n--- Running testimages() ---")
    login_payload = {
        "username": USERNAME,
        "password": PASSWORD
    }
    try:
        response = requests.post(f"{BASE_URL}/login/", json=login_payload, timeout=5, headers={"Content-Type": "application/json"})
        print(f"Login Response Status: {response.status_code}")
        print(f"Login Response Content: {response.text}")
        if response.status_code not in [200, 201]:
            print("Login failed.")
            return
        data = response.json()
        access_token = data.get('data', {}).get('accessToken') or data.get('access')
        if not access_token:
            print("No access token obtained.")
            return
        headers = {'Authorization': f'Bearer {access_token}'}
    except Exception as e:
        print(f"Login error: {e}")
        return

    # 2. Get all bills
    try:
        bills_res = requests.get(f"{BASE_URL}/getbills/", headers=headers, timeout=5)
        if bills_res.status_code != 200:
            print(f"Failed to fetch bills: {bills_res.text}")
            return
        bills = bills_res.json().get('data', [])

        # 3. Find bill starting with 6
        target_bill = None
        for b in bills:
            b_no_str = str(b.get('bill_no', ''))
            if b_no_str.startswith('6'):
                target_bill = b
                break

        if not target_bill:
            print("No bill found starting with '6'. Available bills:", [b.get('bill_no') for b in bills])
            return

        bill_no = target_bill['bill_no']
        print(f"Found target bill no: {bill_no}")

        # 4. Fetch images for this bill
        img_res = requests.get(f"{BASE_URL}/getbill/{bill_no}/images/", headers=headers, timeout=5)
        if img_res.status_code != 200:
            print(f"Failed to fetch images for bill {bill_no}: {img_res.text}")
            return

        images_data = img_res.json().get('data', [])
        if not images_data:
            print(f"No images found for bill {bill_no}")
            return

        download_dir = "/rjdevelopers/downloaded_images"
        os.makedirs(download_dir, exist_ok=True)

        for idx, img_obj in enumerate(images_data):
            img_url_path = img_obj.get('image')
            if not img_url_path:
                continue

            # Since development server doesn't have media static routing, copy directly from backend local storage
            local_file_path = os.path.join("/rjdevelopers/startarun", img_url_path.lstrip("/"))
            if os.path.exists(local_file_path):
                filename = os.path.basename(local_file_path)
                save_path = os.path.join(download_dir, f"bill_{bill_no}_{idx}_{filename}")
                shutil.copy(local_file_path, save_path)
                print(f"Successfully copied image to {save_path}")
            else:
                print(f"Local file not found at: {local_file_path}")

    except Exception as e:
        print(f"Error in testimages: {e}")

if __name__ == '__main__':
    testimages()
