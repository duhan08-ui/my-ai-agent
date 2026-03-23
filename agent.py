import subprocess
import sys
import os
import http.client
import json

# 🔒 GitHub Secrets에서 가져오기
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

def ask_gemini_to_fix(filename, error_msg):
    print("🤖 Gemini AI에게 수리를 요청하는 중...")
    
    with open(filename, 'r', encoding='utf-8') as f:
        code = f.read()

    prompt = f"Fix the Python error below. Output ONLY the fixed code.\nError: {error_msg}\nCode: {code}"
    
    host = "generativelanguage.googleapis.com"
    # ⭐ 현재 가장 가동률이 높은 v1beta와 1.5-flash 조합입니다.
    endpoint = f"/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

    conn = http.client.HTTPSConnection(host)
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    })
    headers = {'Content-Type': 'application/json'}

    try:
        conn.request("POST", endpoint, payload, headers)
        res = conn.getresponse()
        response_text = res.read().decode("utf-8")
        data = json.loads(response_text)

        if 'candidates' in data:
            fixed_code = data['candidates'][0]['content']['parts'][0]['text']
            return fixed_code.replace("```python", "").replace("```", "").strip()
        else:
            print("❌ API 호출 실패! 현재 사용 가능한 모델 목록을 확인합니다...")
            # 🔍 여기서 어떤 모델이 사용 가능한지 서버에 직접 물어봅니다.
            list_endpoint = f"/v1beta/models?key={GEMINI_API_KEY}"
            conn.request("GET", list_endpoint)
            list_res = conn.getresponse().read().decode("utf-8")
            print(f"⚠️ 사용 가능 모델 목록: {list_res}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ 통신 오류: {e}")
        sys.exit(1)

def run_and_fix(filename):
    print(f"🚀 [{filename}] 실행 시도...")
    result = subprocess.run([sys.executable, filename], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ 성공! 결과:\n", result.stdout)
    else:
        print("❌ 에러 발생! AI 분석 시작.")
        fixed_code = ask_gemini_to_fix(filename, result.stderr)
        
        with open(filename, "w", encoding='utf-8') as f:
            f.write(fixed_code)
            
        print(f"🛠️ 자가 수리 완료. 재검증...")
        final_res = subprocess.run([sys.executable, filename], capture_output=True, text=True)
        print(f"✅ 최종 결과: {final_res.stdout if final_res.returncode == 0 else final_res.stderr}")

if __name__ == "__main__":
    with open("happy.py", "w", encoding='utf-8') as f:
        f.write("print(10 / 0)")
    run_and_fix("happy.py")
