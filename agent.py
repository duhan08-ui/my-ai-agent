import subprocess
import sys
import os
import http.client
import json

# 🔒 GitHub Secrets에서 API 키를 안전하게 가져옵니다.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def ask_gemini_to_fix(filename, error_msg):
    print("🤖 Gemini AI에게 수리를 요청하는 중...")
    
    if not GEMINI_API_KEY:
        print("❌ 에러: GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    with open(filename, 'r', encoding='utf-8') as f:
        code = f.read()

    # AI에게 보낼 지시문 (프롬프트)
    prompt = f"""
    다음 파이썬 코드에서 에러가 발생했습니다. 코드를 분석해서 수정해줘.
    
    [에러 메시지]:
    {error_msg}
    
    [원본 코드]:
    {code}
    
    주의사항: 다른 설명은 하지 말고, 오직 수정된 파이썬 코드만 출력해줘. 
    마크다운 기호(```)도 쓰지 마.
    """

    # Google Gemini API 호출 설정
    conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    })
    headers = {'Content-Type': 'application/json'}
    
    # API 요청 보내기
   endpoint = f"/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    conn.request("POST", endpoint, payload, headers)
    
    res = conn.getresponse()
    response_data = res.read().decode("utf-8")
    data = json.loads(response_data)

    # 응답 데이터 분석 및 에러 핸들링
    if 'candidates' not in data:
        print("❌ Gemini API 응답에서 정답을 찾을 수 없습니다.")
        print(f"⚠️ API 응답 내용: {response_data}")
        sys.exit(1)

    # AI가 준 답변 추출 및 정제
    fixed_code = data['candidates'][0]['content']['parts'][0]['text']
    fixed_code = fixed_code.replace("```python", "").replace("```", "").strip()
    
    return fixed_code

def run_and_fix(filename):
    print(f"🚀 [{filename}] 실행 시도 중...")
    
    # 도커 내부가 아닌 현재 파이썬 환경에서 직접 실행
    result = subprocess.run(
        [sys.executable, filename],
        capture_output=True, 
        text=True
    )

    if result.returncode == 0:
        print("✅ 실행 성공! 결과:\n", result.stdout)
    else:
        print("❌ 에러 발생! AI 분석을 시작합니다.")
        error_msg = result.stderr
        print(f"⚠️ 발생한 에러: {error_msg}")
        
        # AI 수리 요청
        fixed_code = ask_gemini_to_fix(filename, error_msg)
        
        # 수리된 코드로 파일 덮어쓰기
        with open(filename, "w", encoding='utf-8') as f:
            f.write(fixed_code)
        
        print(f"🛠️ {filename} 자가 수리 완료. 다시 검증합니다.")
        # 재실행하여 확인
        run_and_fix(filename)

if __name__ == "__main__":
    # 연습용: 일부러 에러가 나는 코드 생성 (0으로 나누기)
    with open("happy.py", "w", encoding='utf-8') as f:
        f.write("print('결과는:', 10 / 0)")
        
    run_and_fix("happy.py")
