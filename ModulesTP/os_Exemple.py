import os

documents_dir_path: str = os.getcwd() + os.sep + "Documents"
file_list: 'list[str]' = os.listdir(documents_dir_path)
first_file_name: str = file_list[0]
first_file_path: str = os.path.join(documents_dir_path, first_file_name)
first_file_size: int = os.path.getsize(first_file_path)
