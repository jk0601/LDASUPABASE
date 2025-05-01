from flask import Flask, render_template, request, jsonify, send_file, Response
from text_mining_analysis import TextMiningAnalysis
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # GUI 없이 이미지 파일만 생성하는 백엔드
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from collections import Counter
import networkx as nx
from wordcloud import WordCloud
import io
import csv
import json
import zipfile
import re
import requests
import uuid
from supabase import create_client, Client

app = Flask(__name__)

# 현재 디렉토리 경로를 기준으로 필요한 파일 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STOPWORDS_PATH = os.path.join(BASE_DIR, 'korean_stopwords.txt')
SENTIMENT_DICT_PATH = os.path.join(BASE_DIR, 'knu_sentiment_lexicon.csv')

# Supabase 설정
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
SUPABASE_BUCKET = 'lda-text-data'  # Supabase 버킷 이름

# Supabase 클라이언트 초기화
supabase = None
try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"Supabase 클라이언트 초기화 성공: {SUPABASE_URL}")
except Exception as e:
    print(f"Supabase 클라이언트 초기화 오류: {str(e)}")
    supabase = None

# 품사 태깅 옵션
POS_OPTIONS = {
    'Noun': '명사',
    'Verb': '동사',
    'Adjective': '형용사',
    'Adverb': '부사',
    'Determiner': '관형사'
}

@app.route('/')
def index():
    return render_template('index.html', pos_options=POS_OPTIONS)

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        # 파일 업로드 처리
        if 'file' not in request.files:
            return jsonify({'error': '파일이 업로드되지 않았습니다.'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '파일이 선택되지 않았습니다.'}), 400
        
        file_data = file.read()
        file_ext = os.path.splitext(file.filename)[1]
        
        # Supabase 활성화된 경우 파일을 Supabase Storage에 업로드
        file_path = ''
        if supabase:
            # Supabase Storage에 업로드할 유니크한 파일명 생성
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            folder_path = "uploads"
            storage_path = f"{folder_path}/{unique_filename}"
            
            # 파일 업로드
            supabase.storage.from_(SUPABASE_BUCKET).upload(
                storage_path,
                file_data
            )
            
            # 업로드된 파일의 임시 URL 가져오기
            file_url = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(storage_path)
            
            # URL로 파일 다운로드하여 임시 파일로 저장
            response = requests.get(file_url)
            temp_file_path = os.path.join(BASE_DIR, 'data', unique_filename)
            os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
            with open(temp_file_path, 'wb') as f:
                f.write(response.content)
            file_path = temp_file_path
        else:
            # Supabase가 없는 경우 로컬 저장
            upload_dir = os.path.join(BASE_DIR, 'data')
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, file.filename)
            with open(file_path, 'wb') as f:
                f.write(file_data)
        
        # 분석 옵션 가져오기
        text_column = request.form.get('text_column', '')
        selected_pos = request.form.getlist('pos_tags')
        stopwords = request.form.get('stopwords', '').split(',')
        stopwords = [word.strip() for word in stopwords if word.strip()]
        
        # 텍스트 마이닝 분석 실행
        analyzer = TextMiningAnalysis(file_path=file_path, text_column=text_column)
        
        # 품사 태깅 및 전처리
        pos_filter = selected_pos if selected_pos else None
        analyzer.preprocess_text(pos_filter=pos_filter, custom_stopwords=stopwords)
        
        # 분석 결과 얻기
        results = {}
        
        # 1. 키워드 추출
        keywords = analyzer.extract_keywords(top_n=20)
        results['keywords'] = [{'word': word, 'freq': freq} for word, freq in keywords.items()]
        
        # 2. TF-IDF 분석
        analyzer.perform_tf_idf_analysis()
        tfidf_keywords = analyzer.get_top_tf_idf_keywords(top_n=20)
        
        # TF-IDF 결과 통합
        all_tfidf_keywords = {}
        for doc_keywords in tfidf_keywords:
            for word, score in doc_keywords:
                if word in all_tfidf_keywords:
                    all_tfidf_keywords[word] = max(all_tfidf_keywords[word], score)
                else:
                    all_tfidf_keywords[word] = score
        
        results['tfidf_keywords'] = [
            {'word': word, 'score': float(score)} 
            for word, score in sorted(all_tfidf_keywords.items(), key=lambda x: x[1], reverse=True)[:20]
        ]
        
        # 3. 토픽 모델링
        topics = analyzer.topic_modeling(num_topics=5, num_words=10)
        results['topics'] = []
        for i, topic in enumerate(topics):
            topic_words = [{'word': word, 'score': float(score)} for word, score in topic]
            results['topics'].append({
                'topic_id': i + 1,
                'words': topic_words
            })
        
        # 4. 감정 분석
        try:
            sentiment = analyzer.sentiment_analysis()
            if isinstance(sentiment, pd.DataFrame):
                sentiment_counts = sentiment['Sentiment'].value_counts()
                results['sentiment'] = {
                    'positive': int(sentiment_counts.get('Positive', 0)),
                    'negative': int(sentiment_counts.get('Negative', 0)),
                    'neutral': int(sentiment_counts.get('Neutral', 0))
                }
            else:
                # 감정 분석 결과가 DataFrame이 아닌 경우 기본값 설정
                results['sentiment'] = {
                    'positive': 0,
                    'negative': 0,
                    'neutral': 0
                }
        except Exception as sentiment_error:
            print(f"감정 분석 오류: {sentiment_error}")
            results['sentiment'] = {
                'positive': 0,
                'negative': 0,
                'neutral': 0
            }
        
        # 5. 워드클라우드 생성
        try:
            # 폰트 경로 설정 (운영체제별 처리)
            font_path = None
            if os.path.exists('C:/Windows/Fonts/malgun.ttf'):  # Windows
                font_path = 'C:/Windows/Fonts/malgun.ttf'
            elif os.path.exists('/usr/share/fonts/truetype/nanum/NanumGothic.ttf'):  # Ubuntu with Nanum
                font_path = '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'
            
            wordcloud = analyzer.create_word_cloud(font_path=font_path)
            
            # 이미지를 바이트 스트림으로 저장
            img_data = io.BytesIO()
            plt.figure(figsize=(10, 5))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.title('전체 키워드 워드클라우드', fontsize=16)
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(img_data, format='png', bbox_inches='tight')
            plt.close()
            img_data.seek(0)
            
            # Supabase가 활성화된 경우 이미지를 Supabase Storage에 업로드
            if supabase:
                image_path = f"images/wordcloud_{uuid.uuid4()}.png"
                supabase.storage.from_(SUPABASE_BUCKET).upload(
                    image_path,
                    img_data.getvalue()
                )
                results['wordcloud_path'] = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(image_path)
            else:
                # 로컬 저장
                wordcloud_path = os.path.join(BASE_DIR, 'static', 'wordcloud.png')
                os.makedirs(os.path.join(BASE_DIR, 'static'), exist_ok=True)
                with open(wordcloud_path, 'wb') as f:
                    f.write(img_data.getvalue())
                results['wordcloud_path'] = '/static/wordcloud.png'
                
        except Exception as wordcloud_error:
            print(f"워드클라우드 생성 오류: {wordcloud_error}")
            results['wordcloud_path'] = ''
            
        # 6. 키워드 네트워크 분석
        try:
            network = analyzer.keyword_network_analysis(threshold=2, top_n=30)
            if network:
                # 네트워크 시각화를 이미지로 저장
                plt.figure(figsize=(10, 8))
                analyzer.plot_network(network)
                
                # 이미지를 바이트 스트림으로 저장
                network_img_data = io.BytesIO()
                plt.savefig(network_img_data, format='png', bbox_inches='tight')
                plt.close()
                network_img_data.seek(0)
                
                # Supabase가 활성화된 경우 이미지를 Supabase Storage에 업로드
                if supabase:
                    network_path = f"images/network_{uuid.uuid4()}.png"
                    supabase.storage.from_(SUPABASE_BUCKET).upload(
                        network_path,
                        network_img_data.getvalue()
                    )
                    results['network_path'] = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(network_path)
                else:
                    # 로컬 저장
                    network_path = os.path.join(BASE_DIR, 'static', 'network.png')
                    with open(network_path, 'wb') as f:
                        f.write(network_img_data.getvalue())
                    results['network_path'] = '/static/network.png'
                
                # 네트워크 노드 정보 추가
                node_data = []
                for node in network.nodes():
                    node_data.append({
                        'word': node,
                        'size': network.nodes[node]['size']
                    })
                results['network_nodes'] = sorted(node_data, key=lambda x: x['size'], reverse=True)[:20]
        except Exception as network_error:
            print(f"키워드 네트워크 분석 오류: {network_error}")
            results['network_path'] = ''
            results['network_nodes'] = []
        
        # 7. 키워드 상관관계 히트맵
        try:
            # 키워드 동시 출현 빈도로 상관관계 계산
            if len(analyzer.tokenized_corpus) > 0:
                # 상위 키워드 추출
                all_words = [word for doc in analyzer.tokenized_corpus for word in doc]
                word_counts = Counter(all_words)
                top_keywords = [word for word, _ in word_counts.most_common(15)]  # 상위 15개 키워드
                
                # 상관관계 행렬 생성
                correlation_matrix = np.zeros((len(top_keywords), len(top_keywords)))
                
                # 동시 출현 빈도 계산
                for i, word1 in enumerate(top_keywords):
                    for j, word2 in enumerate(top_keywords):
                        if i == j:
                            correlation_matrix[i][j] = 1.0  # 대각선은 1로 설정
                        else:
                            # 두 단어가 동시에 나타나는 문서 수 계산
                            cooccurrence = sum(1 for doc in analyzer.tokenized_corpus 
                                            if word1 in doc and word2 in doc)
                            # 정규화
                            doc_with_word1 = sum(1 for doc in analyzer.tokenized_corpus if word1 in doc)
                            doc_with_word2 = sum(1 for doc in analyzer.tokenized_corpus if word2 in doc)
                            
                            if doc_with_word1 > 0 and doc_with_word2 > 0:
                                correlation = cooccurrence / (doc_with_word1 * doc_with_word2) ** 0.5
                                correlation_matrix[i][j] = correlation
                
                # 히트맵 생성 및 이미지 저장
                plt.figure(figsize=(10, 8))
                
                # 한글 폰트 설정
                plt.rcParams['font.family'] = 'Malgun Gothic'
                plt.rcParams['axes.unicode_minus'] = False
                
                sns.heatmap(correlation_matrix, annot=True, cmap='YlGnBu',
                            xticklabels=top_keywords, yticklabels=top_keywords, fmt='.2f')
                plt.title('키워드 상관관계', fontsize=16, fontfamily='Malgun Gothic')
                
                # 이미지를 바이트 스트림으로 저장
                heatmap_img_data = io.BytesIO()
                plt.savefig(heatmap_img_data, format='png', bbox_inches='tight')
                plt.close()
                heatmap_img_data.seek(0)
                
                # Supabase가 활성화된 경우 이미지를 Supabase Storage에 업로드
                if supabase:
                    heatmap_path = f"images/heatmap_{uuid.uuid4()}.png"
                    supabase.storage.from_(SUPABASE_BUCKET).upload(
                        heatmap_path,
                        heatmap_img_data.getvalue()
                    )
                    results['heatmap_path'] = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(heatmap_path)
                else:
                    # 로컬 저장
                    heatmap_path = os.path.join(BASE_DIR, 'static', 'heatmap.png')
                    with open(heatmap_path, 'wb') as f:
                        f.write(heatmap_img_data.getvalue())
                    results['heatmap_path'] = '/static/heatmap.png'
                
                results['correlation_keywords'] = top_keywords
        except Exception as heatmap_error:
            print(f"상관관계 히트맵 생성 오류: {heatmap_error}")
            results['heatmap_path'] = ''
            results['correlation_keywords'] = []
            
        # 8. 긍정/부정 워드클라우드
        try:
            # 감정 분석을 통해 긍정/부정 단어 빈도 계산
            pos_words = {}
            neg_words = {}
            
            for doc in analyzer.tokenized_corpus:
                # 단어별 감정 점수 계산
                for word in doc:
                    sentiment_score = analyzer.knu_dict.get(word, 0)
                    if sentiment_score > 0:  # 긍정 단어
                        pos_words[word] = pos_words.get(word, 0) + 1
                    elif sentiment_score < 0:  # 부정 단어
                        neg_words[word] = neg_words.get(word, 0) + 1
            
            # 긍정 워드클라우드 생성
            if pos_words:
                pos_words_text = ' '.join([f"{word} " * count for word, count in pos_words.items()])
                pos_wordcloud = WordCloud(
                    font_path='C:/Windows/Fonts/malgun.ttf',
                    width=800, 
                    height=400, 
                    background_color='white',
                    max_words=100,
                    colormap='YlGn'  # 녹색 계열 색상
                ).generate(pos_words_text)
                
                # 이미지를 바이트 스트림으로 저장
                pos_cloud_img_data = io.BytesIO()
                plt.figure(figsize=(10, 5))
                plt.imshow(pos_wordcloud, interpolation='bilinear')
                plt.title('긍정 단어 워드클라우드', fontsize=16, fontfamily='Malgun Gothic')
                plt.axis('off')
                plt.tight_layout()
                plt.savefig(pos_cloud_img_data, format='png', bbox_inches='tight')
                plt.close()
                pos_cloud_img_data.seek(0)
                
                # Supabase가 활성화된 경우 이미지를 Supabase Storage에 업로드
                if supabase:
                    pos_cloud_path = f"images/wordcloud_positive_{uuid.uuid4()}.png"
                    supabase.storage.from_(SUPABASE_BUCKET).upload(
                        pos_cloud_path,
                        pos_cloud_img_data.getvalue()
                    )
                    results['pos_wordcloud_path'] = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(pos_cloud_path)
                else:
                    # 로컬 저장
                    pos_cloud_path = os.path.join(BASE_DIR, 'static', 'wordcloud_positive.png')
                    with open(pos_cloud_path, 'wb') as f:
                        f.write(pos_cloud_img_data.getvalue())
                    results['pos_wordcloud_path'] = '/static/wordcloud_positive.png'
            
            # 부정 워드클라우드 생성
            if neg_words:
                neg_words_text = ' '.join([f"{word} " * count for word, count in neg_words.items()])
                neg_wordcloud = WordCloud(
                    font_path='C:/Windows/Fonts/malgun.ttf',
                    width=800, 
                    height=400, 
                    background_color='white',
                    max_words=100,
                    colormap='OrRd'  # 붉은 계열 색상
                ).generate(neg_words_text)
                
                # 이미지를 바이트 스트림으로 저장
                neg_cloud_img_data = io.BytesIO()
                plt.figure(figsize=(10, 5))
                plt.imshow(neg_wordcloud, interpolation='bilinear')
                plt.title('부정 단어 워드클라우드', fontsize=16, fontfamily='Malgun Gothic')
                plt.axis('off')
                plt.tight_layout()
                plt.savefig(neg_cloud_img_data, format='png', bbox_inches='tight')
                plt.close()
                neg_cloud_img_data.seek(0)
                
                # Supabase가 활성화된 경우 이미지를 Supabase Storage에 업로드
                if supabase:
                    neg_cloud_path = f"images/wordcloud_negative_{uuid.uuid4()}.png"
                    supabase.storage.from_(SUPABASE_BUCKET).upload(
                        neg_cloud_path,
                        neg_cloud_img_data.getvalue()
                    )
                    results['neg_wordcloud_path'] = supabase.storage.from_(SUPABASE_BUCKET).get_public_url(neg_cloud_path)
                else:
                    # 로컬 저장
                    neg_cloud_path = os.path.join(BASE_DIR, 'static', 'wordcloud_negative.png')
                    with open(neg_cloud_path, 'wb') as f:
                        f.write(neg_cloud_img_data.getvalue())
                    results['neg_wordcloud_path'] = '/static/wordcloud_negative.png'
        except Exception as sentiment_cloud_error:
            print(f"감정 워드클라우드 생성 오류: {sentiment_cloud_error}")
            results['pos_wordcloud_path'] = ''
            results['neg_wordcloud_path'] = ''
            
        # Supabase가 활성화된 경우 더 이상 필요없는 임시 파일 삭제
        if supabase and os.path.exists(file_path):
            os.remove(file_path)
            
        return jsonify(results)
        
    except Exception as e:
        print(f"분석 오류: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download_csv', methods=['POST'])
def download_csv():
    try:
        # 클라이언트에서 보낸 데이터 가져오기
        data = request.json
        
        # 데이터가 없으면 에러 반환
        if not data:
            return jsonify({"error": "데이터가 없습니다."}), 400
        
        # 데이터를 DataFrame으로 변환
        df = pd.DataFrame(data)
        
        # DataFrame을 CSV로 변환
        csv_data = io.StringIO()
        df.to_csv(csv_data, index=False, encoding='utf-8-sig')
        
        # CSV 파일로 반환
        mem = io.BytesIO()
        mem.write(csv_data.getvalue().encode('utf-8-sig'))
        mem.seek(0)
        
        return send_file(
            mem,
            mimetype='text/csv; charset=utf-8',
            as_attachment=True,
            download_name='텍스트_분석_결과.csv'
        )
    except Exception as e:
        app.logger.error(f"CSV 다운로드 오류: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    try:
        # 클라이언트에서 보낸 HTML 내용
        html_content = request.form.get('html_content')
        
        if not html_content:
            return jsonify({"error": "HTML 내용이 없습니다."}), 400
        
        # 기본 HTML 템플릿에 분석 콘텐츠 추가
        full_html = f'''<!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>텍스트 마이닝 분석 결과</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <style>
                .result-section {{
                    margin-top: 2rem;
                    padding: 1rem;
                    border: 1px solid #dee2e6;
                    border-radius: 0.25rem;
                }}
                body {{
                    font-family: 'Malgun Gothic', sans-serif;
                }}
                img {{
                    max-width: 100%;
                    height: auto;
                }}
            </style>
        </head>
        <body>
            <div class="container mt-5">
                <h1 class="mb-4">텍스트 마이닝 분석 결과</h1>
                {html_content}
            </div>
            <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
        </body>
        </html>'''
        
        # Supabase가 활성화된 경우, 이미지 URL을 그대로 유지
        if supabase:
            modified_html = full_html
        else:
            # 이미지 URL을 상대 경로로 수정 (static/xxx.png 형식)
            modified_html = full_html.replace('src="/static/', 'src="static/')
        
        # ZIP 파일 생성 (HTML + 이미지)
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w') as zf:
            # HTML 파일 추가
            zf.writestr('텍스트_분석_결과.html', modified_html)
            
            # Supabase가 아닌 경우에만 이미지 파일을 ZIP에 포함
            if not supabase:
                # 이미지 파일 추가
                static_dir = os.path.join(BASE_DIR, 'static')
                # HTML에서 사용된 이미지 파일 추출 - 모든 /static/ 경로 찾기
                image_paths = re.findall(r'src="/static/([^"]+)"', html_content)
                
                for img_path in image_paths:
                    file_path = os.path.join(static_dir, img_path)
                    if os.path.exists(file_path):
                        zf.write(file_path, f'static/{img_path}')
                
                # 기본 이미지들도 추가 (혹시 빠진 이미지가 있을 경우)
                for img_name in ['wordcloud.png', 'network.png', 'heatmap.png',
                                'wordcloud_positive.png', 'wordcloud_negative.png',
                                'topic_shares.png', 'centrality_analysis.png',
                                'clustering_analysis.png', 'keyword_influence_bubble.png',
                                'keyword_3d_clusters.png']:
                    img_path = os.path.join(static_dir, img_name)
                    if os.path.exists(img_path) and img_name not in image_paths:
                        zf.write(img_path, f'static/{img_name}')
        
        # 메모리 파일 포인터를 처음으로 되돌림
        memory_file.seek(0)
        
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name='텍스트_분석_결과.zip'
        )
    
    except Exception as e:
        app.logger.error(f"ZIP 다운로드 오류: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, threaded=False, use_reloader=False)
