# 한국어 텍스트 마이닝 분석 도구

이 프로젝트는 한국어 텍스트 데이터의 다양한 분석을 수행하는 웹 애플리케이션입니다.

## 주요 기능

- 키워드 추출 및 빈도 분석
- TF-IDF 분석
- 토픽 모델링 (LDA)
- 감정 분석
- 워드클라우드 생성
- 키워드 네트워크 분석
- 키워드 상관관계 분석
- 중심성 분석
- 클러스터링 분석

## 설치 방법

```bash
# 저장소 클론
git clone https://github.com/jk0601/LDA_TEXT.git
cd LDA_TEXT

# 가상 환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 앱 실행
python app.py
```

## 사용 방법

1. CSV 파일을 업로드합니다.
2. 텍스트 데이터가 포함된 컬럼명을 입력합니다.
3. 품사 태깅 옵션을 선택합니다.
4. 불용어를 설정합니다 (선택사항).
5. '분석 시작' 버튼을 클릭합니다.
6. 분석 결과를 확인하고 다운로드할 수 있습니다.

## 배포

이 애플리케이션은 streamlit을 사용하여 배포할 수 있습니다.

## 라이센스

MIT 라이센스

## 연락처

- 문의사항: jkj0601@gmail.com 

# Supabase 스토리지 연동 안내서

이 안내서는 Supabase Storage를 사용하여 파일을 업로드하고 관리하는 방법을 설명합니다.

## 1. Supabase 프로젝트 설정

### 1.1 스토리지 버킷 생성하기

1. [Supabase 대시보드](https://app.supabase.com)에 로그인합니다.
2. 프로젝트를 선택합니다.
3. 왼쪽 메뉴에서 **Storage**를 클릭합니다.
4. **New Bucket** 버튼을 클릭합니다.
5. 버킷 이름으로 `lda-text-data`를 입력합니다.
6. **Public Bucket** 옵션은 상황에 맞게 선택합니다.
7. **Create Bucket** 버튼을 클릭합니다.

### 1.2 스토리지 폴더 생성하기

1. 생성된 `lda-text-data` 버킷을 클릭합니다.
2. **Create Folder** 버튼을 클릭합니다.
3. 폴더 이름으로 `uploads`를 입력합니다.
4. **Create Folder** 버튼을 클릭합니다.

## 2. 보안 정책(RLS) 설정하기

### 2.1 SQL 편집기를 통한 설정

1. 왼쪽 메뉴에서 **SQL Editor**를 클릭합니다.
2. **New Query** 버튼을 클릭합니다.
3. 아래 SQL 쿼리를 복사하여 붙여넣습니다:

```sql
-- 모든 사용자에게 파일 읽기 권한 부여 (SELECT)
CREATE POLICY "Allow public download from lda-text-data bucket" 
ON storage.objects FOR SELECT 
USING (bucket_id = 'lda-text-data');

-- 모든 사용자에게 파일 업로드 권한 부여 (INSERT)
CREATE POLICY "Allow public upload to lda-text-data bucket" 
ON storage.objects FOR INSERT 
WITH CHECK (bucket_id = 'lda-text-data');

-- uploads 폴더에 파일 업로드 권한 부여 (경로 제한)
CREATE POLICY "Allow upload to uploads folder" 
ON storage.objects FOR INSERT 
WITH CHECK (
  bucket_id = 'lda-text-data' AND 
  (storage.foldername(name))[1] = 'uploads'
);

-- 파일 수정 권한 부여 (UPDATE) - 기존 파일 덮어쓰기 허용
CREATE POLICY "Allow public update to lda-text-data bucket" 
ON storage.objects FOR UPDATE
WITH CHECK (bucket_id = 'lda-text-data');

-- 파일 삭제 권한 부여 (DELETE)
CREATE POLICY "Allow public delete from lda-text-data bucket" 
ON storage.objects FOR DELETE
USING (bucket_id = 'lda-text-data');
```

4. **Run** 버튼을 클릭하여 쿼리를 실행합니다.

### 2.2 UI를 통한 설정 (대안)

SQL 대신 UI를 통해 설정하고 싶다면:

1. 스토리지 페이지에서 **Policies** 탭을 클릭합니다.
2. **New Policy** 버튼을 클릭합니다.
3. **For full customization**을 선택합니다.
4. 각 액션(SELECT, INSERT, UPDATE, DELETE)에 대해 위의 SQL에 해당하는 정책을 설정합니다.

## 3. 환경 변수 설정

애플리케이션에서 Supabase를 사용하기 위해 다음 환경 변수를 설정하세요:

```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_BUCKET=lda-text-data
```

### 3.1 로컬 개발 환경에서 설정

`.env` 파일을 생성하고 다음 내용을 추가합니다:

```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_BUCKET=lda-text-data
```

### 3.2 Vercel에 배포할 경우

1. Vercel 대시보드에서 프로젝트를 선택합니다.
2. **Settings** 탭을 클릭합니다.
3. **Environment Variables**를 클릭합니다.
4. 위의 환경 변수들을 추가합니다.

## 4. 파일 업로드 테스트

1. `test_supabase_storage.py` 스크립트를 실행합니다:
```
python test_supabase_storage.py
```

2. 웹 브라우저에서 http://127.0.0.1:5000 에 접속합니다.
3. CSV 파일을 선택하고 업로드합니다.
4. 업로드가 성공하면 파일 목록에 추가됩니다.

## 5. 문제 해결

### 5.1 RLS 정책 오류

"new row violates row-level security policy" 오류가 발생하면 위에서 설명한 보안 정책 설정이 필요합니다.

### 5.2 인증 오류

Supabase 키를 확인하세요. 익명 키(anon key)를 사용해야 합니다.

### 5.3 버킷 접근 오류

버킷 이름이 올바른지, 해당 버킷이 존재하는지 확인하세요.
