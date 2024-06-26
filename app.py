from flask import Flask, render_template, request, redirect, flash, url_for, send_file, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import json
import os
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from io import BytesIO
import base64
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from google.cloud import storage

# Google Cloud Storage 초기화
def init_storage_client():
    return storage.Client()

storage_client = init_storage_client()
bucket_name = 'guiroman_english_bucket'  # 실제 버킷 이름으로 대체


app = Flask(__name__)
app.secret_key = 'your_secret_key'


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


DATA_FILE = 'data.json'
USERS_FILE = 'users.json'
VOC_FILE = 'voc.json'
CATEGORIES_FILE = 'categories.json'
FONT_PATH = 'templates/NanumGothic.ttf'


def upload_to_gcs(bucket_name, destination_blob_name, data):
    #import pdb; pdb.set_trace()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(data, content_type='application/json')

def download_from_gcs(bucket_name, source_blob_name):
    #import pdb; pdb.set_trace()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    return blob.download_as_string()

def init_file_in_gcs(bucket_name, blob_name, initial_data):
    try:
        download_from_gcs(bucket_name, blob_name)
    except:
        upload_to_gcs(bucket_name, blob_name, json.dumps(initial_data, ensure_ascii=False, indent=4))

init_file_in_gcs(bucket_name, 'data.json', [])
init_file_in_gcs(bucket_name, 'users.json', [])
init_file_in_gcs(bucket_name, 'voc.json', [])
init_file_in_gcs(bucket_name, 'categories.json', {'categories': []})


class User(UserMixin):
   def __init__(self, id):
       self.id = id
       self.password_hash = None


   @staticmethod
   def get(user_id):
       users = json.loads(download_from_gcs(bucket_name, 'users.json').decode('utf-8'))
       user = next((u for u in users if u['id'] == user_id), None)
       if user:
           user_obj = User(user['id'])
           user_obj.password_hash = user['password']
           return user_obj
       return None


   def set_password(self, password):
       self.password_hash = generate_password_hash(password)


   def check_password(self, password):
       return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
   return User.get(user_id)


def autopct_format(values):
   def my_format(pct):
       total = sum(values)
       val = int(round(pct*total/100.0))
       return f'{pct:.1f}%\n({val:d})'
   return my_format


def generate_category_pie_chart(data, main_selected ='', sub_selected=''):
    category_count = {}
    # import pdb; pdb.set_trace()
    if not main_selected:
        for question in data:
            if 'Category' in question and 'main' in question['Category']:
                category = question['Category']['main'] if question['Category']['main'] else '미분류'
                if category in category_count:
                    category_count[category] += 1
                else:
                    category_count[category] = 1
    else:
        main_selected_data = [item for item in data if item["Category"]["main"] == main_selected]
        if not sub_selected:
            for question in main_selected_data:
                if 'Category' in question and 'sub' in question['Category']:
                    category = question['Category']['sub'] if question['Category']['sub'] else '미분류'
                    if category in category_count:
                        category_count[category] += 1
                    else:
                        category_count[category] = 1
        else:
            sub_selected_data = [item for item in data if item["Category"]["sub"] == sub_selected]
            for question in sub_selected_data:
                if 'Category' in question and 'minor' in question['Category']:
                    category = question['Category']['minor'] if question['Category']['minor'] else '미분류'
                    if category in category_count:
                        category_count[category] += 1
                    else:
                        category_count[category] = 1



    labels = list(category_count.keys())
    sizes = list(category_count.values())

    fontprop = fm.FontProperties(fname=FONT_PATH, size=12)

    plt.figure(figsize=(6, 6))
    plt.pie(sizes, labels=labels, autopct=autopct_format(sizes), startangle=140)

    # 라벨에 폰트 적용
    for label in plt.gca().texts:
        label.set_fontproperties(fontprop)

    plt.tight_layout()
    img = BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    img_base64 = base64.b64encode(img.getvalue()).decode()
    plt.close()
    return img_base64

@app.route('/updateChart', methods=['GET'])
@login_required
def updateChart():
    # import pdb; pdb.set_trace()
    data = json.loads(download_from_gcs(bucket_name, 'data.json').decode('utf-8'))
    main_selected = request.args.get('mainCategory', 1)
    sub_selected = request.args.get('subCategory', 1)
    chart_base64 = generate_category_pie_chart(data, main_selected, sub_selected)
    return chart_base64



@app.route('/')
@login_required
def index():
    data = json.loads(download_from_gcs(bucket_name, 'data.json').decode('utf-8'))
    if current_user.id == 'admin':
        user_questions = data
    else:
        user_questions = [q for q in data if q['SubmitterID'] == current_user.id]

    last_type = request.cookies.get('last_type')
    last_category = {
        'main': request.cookies.get('last_main_category', ''),
        'sub': request.cookies.get('last_sub_category', ''),
        'minor': request.cookies.get('last_minor_category', '')
    }
    last_tags = request.cookies.get('last_tags')
    last_source = request.cookies.get('last_source', '')

    for question in user_questions:
        if 'Source' not in question:
            question['Source'] = '출처 없음'
        if 'SubmissionTime' not in question:
            question['SubmissionTime'] = 'N/A'
        if 'LastModifiedTime' not in question or not question['LastModifiedTime']:
            question['LastModifiedTime'] = '수정되지 않음'

    chart_base64 = generate_category_pie_chart(data)  # 전체 문제 데이터 사용
    return render_template('index.html', questions=user_questions, user=current_user, last_type=last_type, last_category=last_category, last_tags=last_tags, last_source=last_source, chart_base64=chart_base64, total_questions=len(data))





@app.route('/register', methods=['GET', 'POST'])
def register():
   if request.method == 'POST':
       user_id = request.form['user_id']
       password = request.form['password']
       user = User.get(user_id)
       if user is not None:
           flash('User ID already exists.', 'error')
       else:
           user = User(user_id)
           user.set_password(password)
           users = json.loads(download_from_gcs(bucket_name, 'users.json').decode('utf-8'))
           users.append({'id': user_id, 'password': user.password_hash})
           upload_to_gcs(bucket_name, 'users.json', json.dumps(users, ensure_ascii=False, indent=4))
           flash('User registered successfully!', 'success')
           return redirect(url_for('login'))
   return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
   #import pdb; pdb.set_trace()
   if request.method == 'POST':
       user_id = request.form['user_id']
       password = request.form['password']
       user = User.get(user_id)
       if user is None or not user.check_password(password):
           flash('Invalid user ID or password.', 'error')
       else:
           login_user(user)
           response = redirect(url_for('index'))
           response.set_cookie('last_type', '', expires=0)
           response.set_cookie('last_main_category', '', expires=0)
           response.set_cookie('last_sub_category', '', expires=0)
           response.set_cookie('last_minor_category', '', expires=0)
           response.set_cookie('last_tags', '', expires=0)

           return response
   return render_template('login.html')

# @app.route('/login', methods=['GET', 'POST'])
# def login():
#     if request.method == 'POST':
#         try:
#             user_id = request.form['user_id']
#             password = request.form['password']
#             user = User.get(user_id)
#             if user is None or not user.check_password(password):
#                 flash('Invalid user ID or password.', 'error')
#                 return redirect(url_for('login'))
#             login_user(user)
#             return redirect(url_for('index'))
#         except Exception as e:
#             flash(f'An error occurred: {str(e)}', 'error')
#             return redirect(url_for('login'))
#     return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    response = redirect(url_for('login'))
    response.set_cookie('last_type', '', expires=0)
    response.set_cookie('last_main_category', '', expires=0)
    response.set_cookie('last_sub_category', '', expires=0)
    response.set_cookie('last_minor_category', '', expires=0)
    response.set_cookie('last_tags', '', expires=0)

    return response


from werkzeug.utils import secure_filename

UPLOAD_FOLDER = '/tmp/image_data'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def save_image(file, filename):
    if file:
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], str(filename.split('_')[-1].split('.')[0]))
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        filepath = os.path.join(folder_path, filename)
        file.save(filepath)
        return filepath
    return None

@app.route('/submit', methods=['POST'])
@login_required
def submit_question():
    question_type = request.form['question_type']
    choices = []

    if question_type == 'multiple':
        question = request.form['mc_question']
        choices = request.form.getlist('mc_choices[]')
        answers = request.form.getlist('mc_answers[]')
    elif question_type == 'subjective':
        question = request.form['sub_question']
        answer = request.form['sub_answer']
        answers = [answer]
    elif question_type == 'fill_in_the_blank':
        question = request.form['fib_question']
        raw_answers = request.form.getlist('fib_answer[]')
        others = request.form.getlist('fib_others[]')
        answers = {f"Blank#{i + 1}": answer for i, answer in enumerate(raw_answers)}
        for i, other in enumerate(others):
            answers[f"other#{i + 1}"] = other  # Add each other choice with a unique key

    main_category = request.form['main_category']
    sub_category = request.form['sub_category']
    minor_category = request.form['minor_category']
    tags = request.form['tags']
    source = request.form['source']



    try:
        data = json.loads(download_from_gcs(bucket_name, 'data.json').decode('utf-8'))

        new_id = max([item['ID'] for item in data], default=0) + 1 if data else 1

        new_data = {
            'ID': new_id,
            'Type': question_type,
            'Question': question,
            'Choices': choices,
            'Answers': answers,
            'SubmitterID': current_user.id,
            'Category': {
                'main': main_category,
                'sub': sub_category,
                'minor': minor_category
            },
            'Tags': tags,
            'Source': source,
            'SubmissionTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'LastModifiedTime': ''
        }

        data.append(new_data)

        upload_to_gcs(bucket_name, 'data.json', json.dumps(data, ensure_ascii=False, indent=4))

        flash('Question successfully submitted!', 'success')
        response = redirect(url_for('index'))
        response.set_cookie('last_type', question_type)
        response.set_cookie('last_main_category', main_category)
        response.set_cookie('last_sub_category', sub_category)
        response.set_cookie('last_minor_category', minor_category)
        response.set_cookie('last_tags', tags)

        return response
    except Exception as e:
        flash(f'An error occurred while submitting the question: {e}', 'error')

    return redirect(url_for('index'))



@app.route('/edit/<int:question_id>', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    data = json.loads(download_from_gcs(bucket_name, 'data.json').decode('utf-8'))
    
    # 기존 데이터를 찾음
    question = next((q for q in data if q['ID'] == question_id and (q['SubmitterID'] == current_user.id or current_user.id == 'admin')), None)
    
    if question is None:
        flash('Question not found or you do not have permission to edit it.', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        question_type = request.form['question_type']
        new_question = {}
        
        # 폼 데이터를 바탕으로 새로운 데이터를 생성
        if question_type == 'multiple':
            new_question = {
                'Question': request.form['mc_question'],
                'Choices': request.form.getlist('mc_choices[]'),
                'Answers': request.form.getlist('mc_answers[]')
            }
        elif question_type == 'subjective':
            new_question = {
                'Question': request.form['sub_question'],
                'Answers': [request.form['sub_answer']],
                'Choices': None
            }
        elif question_type == 'fill_in_the_blank':
            raw_answers = request.form.getlist('fib_answer[]')
            other_choices = request.form.getlist('fib_others[]')
            answers = {f"Blank#{i + 1}": answer for i, answer in enumerate(raw_answers)}
            for i, other in enumerate(other_choices):
                answers[f"other#{i + 1}"] = other  # Add each other choice with a unique key
            
            new_question = {
                'Question': request.form['fib_question'],
                'Answers': answers,
                'Choices': None
            }
        
        # 카테고리, 태그, 출처, 시간 정보 등을 설정
        new_question.update({
            'ID': question['ID'],  # 기존 ID 유지
            'Type': question_type,
            'SubmitterID': current_user.id,
            'Category': {
                'main': request.form['main_category'],
                'sub': request.form['sub_category'],
                'minor': request.form['minor_category']
            },
            'Tags': request.form['tags'],
            'Source': request.form['source'],
            'SubmissionTime': question['SubmissionTime'],  # 기존 제출 시간 유지
            'LastModifiedTime': datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # 현재 시간으로 수정 시간 설정
        })
        
        # 기존 데이터를 덮어쓰지 않고 새로운 데이터를 생성하여 리스트에 저장
        data = [q if q['ID'] != question_id else new_question for q in data]
        
        # 데이터 파일에 저장
        upload_to_gcs(bucket_name, 'data.json', json.dumps(data, ensure_ascii=False, indent=4))
        
        flash('Question successfully updated!', 'success')
        return redirect(url_for('index'))
    
    return render_template('edit_question.html', question=question)








import shutil

@app.route('/delete/<int:question_id>', methods=['POST'])
@login_required
def delete_question(question_id):
    try:
        data = json.loads(download_from_gcs(bucket_name, 'data.json').decode('utf-8'))
        question = next((q for q in data if q['ID'] == question_id and (q['SubmitterID'] == current_user.id or current_user.id == 'admin')), None)
        if question:
            folder_path = os.path.join(app.config['UPLOAD_FOLDER'], str(question_id))
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
            data = [q for q in data if q['ID'] != question_id]
            upload_to_gcs(bucket_name, 'data.json', json.dumps(data, ensure_ascii=False, indent=4))

            flash('Question and associated images successfully deleted!', 'success')
        else:
            flash('Question not found or you do not have permission to delete it.', 'error')
    except Exception as e:
        flash(f'An error occurred while deleting the question: {e}', 'error')
    return redirect(url_for('index'))

@app.route('/delete_image', methods=['POST'])
@login_required
def delete_image():
    try:
        data = request.get_json()
        question_id = data['question_id']
        image_type = data['image_type']
        filename_map = {
            'question_image': f'img_question_{question_id}.png',
            'answer_image': f'img_answer_{question_id}.png'
        }
        if 'choice_image_' in image_type:
            choice_num = image_type.split('_')[2]
            filename_map[image_type] = f'img_choice_{choice_num}_{question_id}.png'
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], str(question_id), filename_map[image_type])
        if os.path.exists(image_path):
            os.remove(image_path)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, error=str(e))



@app.route('/submit_voc', methods=['POST'])
@login_required
def submit_voc():
   voc_type = request.form['voc_type']
   voc_content = request.form['voc_content']


   new_voc = {
       'Type': voc_type,
       'Content': voc_content,
       'SubmitterID': current_user.id
   }


   try:
       voc_data = json.loads(download_from_gcs(bucket_name, 'voc.json').decode('utf-8'))
      
       voc_data.append(new_voc)
      
       upload_to_gcs(bucket_name, 'voc.json', json.dumps(voc_data, ensure_ascii=False, indent=4))


       flash('VOC successfully submitted!', 'success')
   except Exception as e:
       flash(f'An error occurred while submitting the VOC: {e}', 'error')
  
   return redirect(url_for('index'))


@app.route('/download_voc')
@login_required
def download_voc():
   return send_file(VOC_FILE, as_attachment=True)


@app.route('/download')
@login_required
def download():
   return send_file(DATA_FILE, as_attachment=True)


@app.route('/download_users')
@login_required
def download_users():
   if current_user.id == 'admin':
       return send_file(USERS_FILE, as_attachment=True)
   else:
       flash('You do not have permission to download this file.', 'error')
       return redirect(url_for('index'))


@app.route('/download_categories')
@login_required
def download_categories():
   return send_file(CATEGORIES_FILE, as_attachment=True)


@app.route('/categories', methods=['GET'])
@login_required
def get_categories():
   categories = json.loads(download_from_gcs(bucket_name, 'categories.json').decode('utf-8'))
   return jsonify(categories)


@app.route('/manage_categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
   if current_user.id != 'admin':
       flash('You do not have permission to manage categories.', 'error')
       return redirect(url_for('index'))


   if request.method == 'POST':
       categories_content = request.form['categories_content']
       try:
           categories = json.loads(categories_content)
           upload_to_gcs(bucket_name, 'categories.json', json.dumps(categories, ensure_ascii=False, indent=4))
           flash('Categories updated successfully!', 'success')
       except json.JSONDecodeError:
           flash('Invalid JSON format.', 'error')
  
   categories = json.loads(download_from_gcs(bucket_name, 'categories.json').decode('utf-8'))
   return render_template('manage_categories.html', categories=json.dumps(categories, ensure_ascii=False, indent=4))


@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
   if request.method == 'POST':
       old_password = request.form['old_password']
       new_password = request.form['new_password']
       confirm_password = request.form['confirm_password']


       user = User.get(current_user.id)


       if not user.check_password(old_password):
           flash('Old password is incorrect.', 'error')
       elif new_password != confirm_password:
           flash('New passwords do not match.', 'error')
       else:
           user.set_password(new_password)
           users = json.loads(download_from_gcs(bucket_name, 'users.json').decode('utf-8'))
           for u in users:
               if u['id'] == user.id:
                   u['password'] = user.password_hash
                   break
           upload_to_gcs(bucket_name, 'users.json', json.dumps(users, ensure_ascii=False, indent=4))
           flash('Password changed successfully!', 'success')
           return redirect(url_for('index'))
   return render_template('change_password.html')


if __name__ == '__main__':
   app.run(debug=True, host='0.0.0.0', port=4444)
