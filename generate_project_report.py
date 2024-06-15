import os

def get_project_structure(root_dir, exclude_files, exclude_dirs):
    exclude_files = set(os.path.abspath(f) for f in exclude_files)
    exclude_dirs = set(os.path.abspath(d) for d in exclude_dirs)
    
    structure_lines = ["Project structure", "-----------------"]
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if os.path.abspath(os.path.join(root, d)) not in exclude_dirs]
        level = root.replace(root_dir, '').count(os.sep)
        indent = ' ' * 4 * level
        structure_lines.append(f"{indent}{os.path.basename(root)}/")
        sub_indent = ' ' * 4 * (level + 1)
        for file in files:
            file_path = os.path.abspath(os.path.join(root, file))
            if file_path not in exclude_files:
                structure_lines.append(f"{sub_indent}{file}")
    return '\n'.join(structure_lines)

def get_file_structure_and_contents(root_dir, exclude_files=None, exclude_dirs=None):
    if exclude_files is None:
        exclude_files = []
    if exclude_dirs is None:
        exclude_dirs = []

    exclude_files = set(os.path.abspath(f) for f in exclude_files)
    exclude_dirs = set(os.path.abspath(d) for d in exclude_dirs)
    
    project_structure = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if os.path.abspath(os.path.join(root, d)) not in exclude_dirs]
        
        level = root.replace(root_dir, '').count(os.sep)
        indent = ' ' * 4 * level
        project_structure.append(f"{indent}{os.path.basename(root)}/")
        sub_indent = ' ' * 4 * (level + 1)
        for file in files:
            file_path = os.path.abspath(os.path.join(root, file))
            if file_path not in exclude_files:
                project_structure.append(f"{sub_indent}{file}")
                project_structure.append(f"{sub_indent}{'-'*len(file)}")  # 파일 제목 구분선
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    content_lines = content.splitlines()
                    for line in content_lines:
                        project_structure.append(f"{sub_indent}{line}")
                project_structure.append('')  # 파일 간의 개행 추가
    return '\n'.join(project_structure)

def write_to_file(header_content, content, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(header_content)
        f.write('\n\n')
        f.write(content)

if __name__ == "__main__":
    root_directory = "."  # 현재 디렉토리
    
    # 제외할 파일들 리스트
    exclude_files = [
        'templates/.bashrc',
        'templates/NanumGothic.ttf',
        'categories.json',
        'data.json',
        'generate_project_report.py',
        'users.json',
        'voc.json',
        'project_structure_and_contents.txt'
    ]
    
    # 제외할 폴더들 리스트
    exclude_dirs = [
        'image_data',
        'static/image_data',
        '.git',
        '..'
    ]
    
    # 절대 경로로 변환
    exclude_files = [os.path.abspath(file) for file in exclude_files]
    exclude_dirs = [os.path.abspath(folder) for folder in exclude_dirs]
    
    output_file = "project_structure_and_contents.txt"
    
    project_structure_header = get_project_structure(root_directory, exclude_files, exclude_dirs)
    project_structure = get_file_structure_and_contents(root_directory, exclude_files, exclude_dirs)
    write_to_file(project_structure_header, project_structure, output_file)
    print(f"Project structure and contents have been written to {output_file}")