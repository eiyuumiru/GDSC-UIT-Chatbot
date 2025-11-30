from google.cloud import storage
import os

def get_bucket(bucket_name: str):
    client = storage.Client.create_anonymous_client()
    bucket = client.bucket(bucket_name)
    print(f"Đang kết nối vào bucket: {bucket.name}")

    blobs = client.list_blobs(bucket_name, prefix="Output/")

    # Tạo thư mục trên máy tính để chứa file tải về
    local_folder = "ai/dataset/CS311"
    if not os.path.exists(local_folder):
        os.makedirs(local_folder)

    print(f"--- Bắt đầu tải về thư mục '{local_folder}' ---")

    for blob in blobs:
        if blob.name.endswith(".json"):
            filename = os.path.basename(blob.name)
            
            local_path = os.path.join(local_folder, filename)
            
            if os.path.exists(local_path):
                print(f"Bỏ qua (đã tồn tại): {filename}")
                continue
            
            print(f"Đang lưu file: {filename}")
            
            blob.download_to_filename(local_path)

    print("Hoàn tất!")