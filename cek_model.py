import google.generativeai as genai

# GANTI DENGAN API KEY YANG BARU (JANGAN PAKE YANG LAMA)
API_KEY = 'AIzaSyAq-Mv9xjMpULeCGbzTUnGbGRMmOTeuDQE'

genai.configure(api_key=API_KEY)

print("sedang mengecek daftar model AI...")

try:
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- Ditemukan: {m.name}")
            available_models.append(m.name)
            
    if not available_models:
        print("\nModel tidak ditemukan. Cek API Key atau koneksi internet.")
    else:
        print(f"\nSukses! Ada {len(available_models)} model yang bisa dipake.")

except Exception as e:
    print(f"\nERROR PARAH: {e}")