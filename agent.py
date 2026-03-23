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

    # AI에게 보낼 요청 데이터 구성
    prompt = f"Fix the following Python error. Output ONLY the fixed code.\nError: {error_msg}\nCode: {code}"
    
    # 🔗 구글이 권장하는 가장 표준적인 REST API 주소 체계
    host = "generativelanguage.googleapis.com"
    # 모델명에서 '-latest'나 버전 숫자를 모두 빼고 가장 기본형을 씁니다.
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

        # 성공적으로 답변을 받았을 때
        if 'candidates' in data:
            fixed_code = data['candidates'][0]['content']['parts'][0]['text']
            # 불필요한 마크다운 기호 제거
            return fixed_code.replace("```python", "").replace("```", "").strip()
        else:
            # ❌ 만약 또 404가 나면 로그에 상세 원인 출력
            print(f"❌ API 응답 실패: {response_text}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ 통신 중 오류 발생: {e}")
        sys.exit(1)

def run_and_fix(filename):
    print(f"🚀 [{filename}] 실행 시도...")
    result = subprocess.run([sys.executable, filename], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ 성공! 결과:\n", result.stdout)
    else:
        print("❌ 에러 발생! AI에게 수리를 요청합니다.")
        fixed_code = ask_gemini_to_fix(filename, result.stderr)
        
        with open(filename, "w", encoding='utf-8') as f:
            f.write(fixed_code)
            
        print(f"🛠️ {filename} 자가 수리 완료. 다시 검증합니다.")
        # 재실행 확인
        final_res = subprocess.run([sys.executable, filename], capture_output=True, text=True)
        print(f"✅ 최종 결과: {final_res.stdout if final_res.returncode == 0 else final_res.stderr}")

if __name__ == "__main__":
    # 에러 유발 파일 생성
    with open("happy.py", "w", encoding='utf-8') as f:
        f.write("print(10 / 0)")
    run_and_fix("happy.py")
