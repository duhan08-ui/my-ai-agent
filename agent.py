import subprocess
import sys
import os
import http.client
import json

# 🔑 여기에 발급받은 API 키를 넣으세요!
GEMINI_API_KEY = "mythical-legend-431904-g4"

def ask_gemini_to_fix(filename, error_msg):
    print("🤖 Gemini AI에게 수리를 요청하는 중...")
    
    with open(filename, 'r') as f:
        code = f.read()

    # AI에게 보낼 질문(프롬프트)
    prompt = f"다음 파이썬 코드에서 발생한 에러를 고쳐줘.\n\n[에러 메시지]:\n{error_msg}\n\n[원본 코드]:\n{code}\n\n다른 설명 없이 오직 수정된 파이썬 코드만 출력해줘."

    # Google Gemini API 호출 (라이브러리 없이 순수 HTTP 요청)
    conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    })
    headers = {'Content-Type': 'application/json'}
    
    conn.request("POST", f"/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}", payload, headers)
    res = conn.getresponse()
    data = json.loads(res.read().decode("utf-8"))
    
    # AI가 준 답변에서 코드만 추출
    fixed_code = data['candidates'][0]['content']['parts'][0]['text']
    # 마크다운 기호(```python 등) 제거
    fixed_code = fixed_code.replace("```python", "").replace("```", "").strip()
    return fixed_code

def run_and_fix(filename):
    print(f"🚀 [{filename}] 실행 시도 중...")
    result = subprocess.run([sys.executable, filename], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ 실행 성공! 결과:\n", result.stdout)
    else:
        print("❌ 에러 발생!")
        error_msg = result.stderr
        
        # 진짜 AI에게 물어봐서 코드를 받아옴
        fixed_code = ask_gemini_to_fix(filename, error_msg)
        
        with open(filename, "w", encoding='utf-8') as f:
            f.write(fixed_code)
        
        print(f"🛠️ AI가 {filename}을 수리했습니다. 다시 실행합니다.")
        run_and_fix(filename)

if __name__ == "__main__":
    # 연습용: 0으로 나누기 에러가 나는 코드 생성
    with open("happy.py", "w", encoding='utf-8') as f:
        f.write("print(10 / 0) # 0으로 나누기 에러 발생!")
        
    run_and_fix("happy.py")
