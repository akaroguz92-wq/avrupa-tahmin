import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime, timedelta

# --- BAĞLANTI AYARLARI ---
# Supabase URL ve Key bilgilerini buraya gireceksin
url = "SENİN_SUPABASE_URL_ADRESİ"
key = "SENİN_SUPABASE_ANON_KEY_BİLGİN"
supabase = create_client(url, key)

st.set_page_config(page_title="Avrupa Maç Tahmin", layout="wide")

# --- YARDIMCI FONKSİYONLAR ---
def calculate_points(prediction, result, odds_dict):
    if not result or prediction != result:
        return 0
    raw_odds = odds_dict.get(result.lower(), 1.0)
    return min(raw_odds * 10, 50.0)

# --- ARAYÜZ ---
st.title("🏆 Avrupa Maç Tahmin Yarışması")

menu = st.sidebar.selectbox("Menü", ["Liderlik Tablosu", "Tahmin Yap", "Maç Sonuçları (Admin)"])
user = st.sidebar.selectbox("Oyuncu", ["Ahmet", "Mehmet", "Ali", "Veli"])

# --- 1. LİDERLİK TABLOSU ---
if menu == "Liderlik Tablosu":
    st.header("📊 Genel Puan Durumu")
    
    # Tüm tahminleri ve maçları çek
    preds = supabase.table("predictions").select("*").execute().data
    matches = supabase.table("matches").select("*").execute().data
    
    # Oyuncu bazlı hesaplama
    stats = []
    for player in ["Ahmet", "Mehmet", "Ali", "Veli"]:
        user_preds = [p for p in preds if p['user_name'] == player]
        total_p = 0
        correct_count = 0
        odds_3_plus = 0
        max_single = 0
        
        for p in user_preds:
            m = next((m for m in matches if m['id'] == p['match_id']), None)
            if m and m['result']:
                # Puanı hesapla
                odds_map = {'g': m['odds_g'], 'b': m['odds_b'], 'm': m['odds_m']}
                pts = calculate_points(p['prediction'], m['result'], odds_map)
                
                if pts > 0:
                    total_p += pts
                    correct_count += 1
                    max_single = max(max_single, pts)
                    # Kural 9.2: 3.00 ve üzeri oranlı tahmin
                    actual_odd = odds_map.get(m['result'].lower(), 0)
                    if actual_odd >= 3.00:
                        odds_3_plus += 1
                        
        stats.append({
            "Oyuncu": player,
            "Toplam Puan": total_p,
            "Doğru Sayısı": correct_count,
            "3.00+ Oran": odds_3_plus,
            "En Yüksek Maç": max_single
        })
    
    df = pd.DataFrame(stats)
    # Kural 9: Eşitlik bozma sırası
    df = df.sort_values(by=["Toplam Puan", "Doğru Sayısı", "3.00+ Oran", "En Yüksek Maç"], ascending=False)
    
    # Kazanan/Kaybeden Belirleme (Kural 2 & 15)
    df['Durum'] = ["💰 Kazanan (1.)", "💰 Kazanan (2.)", "🍴 Ismarlıyor (3.)", "🍴 Ismarlıyor (4.)"]
    st.table(df)
    st.warning("🍴 3. ve 4. oyuncular, Mahir Lokantası'nda hesabın tamamını öder!")

# --- 2. TAHMİN YAPMA (KAPALI SİSTEM) ---
elif menu == "Tahmin Yap":
    st.header("📝 Tahmin Girişi")
    active_matches = supabase.table("matches").select("*").filter("result", "is", "null").execute().data
    
    for m in active_matches:
        m_time = datetime.fromisoformat(m['match_time'])
        deadline = m_time - timedelta(minutes=30)
        
        st.subheader(f"{m['teams']}")
        st.write(f"⏰ Son Tarih: {deadline.strftime('%d.%m %H:%M')}")
        
        if datetime.now() < deadline:
            choice = st.radio(f"Tahminin ({m['teams']})", ["G", "B", "M"], key=m['id'], horizontal=True)
            if st.button(f"Kaydet: {m['teams']}"):
                # Mevcut tahmini sil ve yenisini ekle
                supabase.table("predictions").delete().match({"match_id": m['id'], "user_name": user}).execute()
                supabase.table("predictions").insert({
                    "match_id": m['id'], "user_name": user, "prediction": choice
                }).execute()
                st.success("Tahminin başarıyla kaydedildi (Kapalı Sistem)!")
        else:
            st.error("Süre doldu, tahmin yapılamaz.")

# --- 3. ADMIN (SONUÇ GİRİŞİ) ---
elif menu == "Maç Sonuçları (Admin)":
    st.header("⚙️ Admin - Maç ve Sonuç Yönetimi")
    # Maç Ekleme ve Sonuçlandırma buraya gelecek...
