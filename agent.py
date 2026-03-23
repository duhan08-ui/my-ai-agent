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

    prompt = f"다음 파이썬 코드의 에러를 수정해줘. 코드만 출력해.\n\n[에러]:\n{error_msg}\n\n[코드]:\n{code}"

    conn = http.client.HTTPSConnection("generativelanguage.googleapis.com")
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    })
    headers = {'Content-Type': 'application/json'}
    
    # ⭐ 404 해결 포인트: 모델명 앞에 'models/'를 붙이지 않고 호출해봅니다.
    # 혹은 v1beta를 사용하되 주소를 가장 단순화합니다.
    endpoint = f"/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    try:
        conn.request("POST", endpoint, payload, headers)
        res = conn.getresponse()
        response_data = res.read().decode("utf-8")
        data = json.loads(response_data)

        if 'candidates' not in data:
            # 💡 만약 또 404가 나면 다른 모델명으로 즉시 재시도하는 로직
            print("🔄 모델명을 변경하여 재시도 중 (gemini-pro)...")
            alt_endpoint = f"/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
            conn.request("POST", alt_endpoint, payload, headers)
            res = conn.getresponse()
            response_data = res.read().decode("utf-8")
            data = json.loads(response_data)

        # 응답 추출
        fixed_code = data['candidates'][0]['content']['parts'][0]['text']
        return fixed_code.replace("```python", "").replace("```", "").strip()

    except Exception as e:
        print(f"❌ 통신 에러: {e}")
        print(f"⚠️ 응답 내용: {response_data}")
        sys.exit(1)

def run_and_fix(filename):
    print(f"🚀 [{filename}] 실행 시도 중...")
    result = subprocess.run([sys.executable, filename], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ 실행 성공! 결과:\n", result.stdout)
    else:
        print("❌ 에러 발생! AI 분석 시작.")
        fixed_code = ask_gemini_to_fix(filename, result.stderr)
        with open(filename, "w", encoding='utf-8') as f:
            f.write(fixed_code)
        print(f"🛠️ {filename} 자가 수리 완료. 재검증합니다.")
        run_and_fix(filename)

if __name__ == "__main__":
    with open("happy.py", "w", encoding='utf-8') as f:
        f.write("print('결과는:', 10 / 0)")
    run_and_fix("happy.py")

