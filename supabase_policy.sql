-- Supabase Storage 보안 정책 설정
-- SQL 편집기에서 이 쿼리를 실행하세요.

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