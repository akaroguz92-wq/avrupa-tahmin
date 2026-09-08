import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime, timedelta

# --- BAĞLANTI AYARLARI ---
URL = "https://lwcizmvxedoqxxnvgffe.supabase.co"
KEY = "sb_publishable_aW7OvAbRww2wCFh5yRJ5Jw_WxC24xPv"
supabase = create_client(URL, KEY)

st.set_page_config(page_title="Avrupa Maç Tahmin Yarışması", layout="wide")

# --- YARDIMCI FONKSİYONLAR ---
def calculate_points(prediction, result, odds):
    if not result or prediction != result:
        return 0
    # Kural 6: Puan = min(Oran * 10, 50)
    raw_points = odds.get(result.lower(), 0) * 10
    return min(raw_points, 50.0)

# --- ARAYÜZ ---
st.sidebar.title("🏆 Avrupa Yarışması")
menu = st.sidebar.radio("Menü", ["📊 Puan Durumu", "📝 Tahmin Yap", "⚽ Maç Ekle/Sonuçlandır"])
user = st.sidebar.selectbox("Oyuncu Seçiniz", ["Oğuz", "Recep", "Semih", "İbo"])

# --- 1. PUAN DURUMU ---
if menu == "📊 Puan Durumu":
    st.header("📊 Genel Puan Durumu (Toplam Puan)")
    
    matches = supabase.table("matches").select("*").execute().data
    preds = supabase.table("predictions").select("*").execute().data
    
    stats = []
    for player in ["Oğuz", "Recep", "Semih", "İbo"]:
        user_preds = [p for p in preds if p['user_name'] == player]
        total_p = 0
        correct_count = 0
        high_odds_count = 0
        max_single = 0
        
        for p in user_preds:
            m = next((m for m in matches if m['id'] == p['match_id']), None)
            if m and m['result']:
                odds_map = {'g': m['odds_g'], 'b': m['odds_b'], 'm': m['odds_m']}
                puan = calculate_points(p['prediction'], m['result'], odds_map)
                
                if puan > 0:
                    total_p += puan
                    correct_count += 1
                    max_single = max(max_single, puan)
                    if odds_map[m['result'].lower()] >= 3.00:
                        high_odds_count += 1
                        
        stats.append({
            "Oyuncu": player,
            "Toplam Puan": total_p,
            "Doğru": correct_count,
            "3.00+ Oran Bilme": high_odds_count,
            "En Yüksek Tek Maç": max_single
        })
    
    df = pd.DataFrame(stats)
    # Kural 9: Eşitlik Bozma Kriterleri
    df = df.sort_values(by=["Toplam Puan", "Doğru", "3.00+ Oran Bilme", "En Yüksek Tek Maç"], ascending=False)
    
    # Kural 15: Mahir Lokantası Etiketi
    df['Durum'] = ["💰 Kazanan (1.)", "💰 Kazanan (2.)", "🍴 Ismarlıyor (3.)", "🍴 Ismarlıyor (4.)"]
    
    st.table(df)
    st.info("💡 Puanlar her maçtan alınan değerlerin toplanmasıyla ilerler.")

# --- 2. TAHMİN YAP ---
elif menu == "📝 Tahmin Yap":
    st.header("📝 Maç Tahminlerini Gir")
    # Henüz sonucu girilmemiş maçları getir
    matches = supabase.table("matches").select("*").filter("result", "is", "null").execute().data
    
    if not matches:
        st.write("Şu an aktif maç bulunmamaktadır.")
    
    for m in matches:
        m_time = datetime.fromisoformat(m['match_time'])
        deadline = m_time - timedelta(minutes=30)
        
        st.subheader(f"{m['teams']}")
        st.write(f"Oranlar: G: {m['odds_g']} | B: {m['odds_b']} | M: {m['odds_m']}")
        st.write(f"📅 Maç Zamanı: {m_time.strftime('%d.%m.%Y %H:%M')}")
        
        if datetime.now() < deadline:
            # Mevcut tahmini kontrol et
            existing = supabase.table("predictions").select("prediction").match({"match_id": m['id'], "user_name": user}).execute().data
            default_index = 0
            if existing:
                map_idx = {"G": 0, "B": 1, "M": 2}
                default_index = map_idx.get(existing[0]['prediction'], 0)
            
            choice = st.radio(f"Tahminin ({m['teams']})", ["G", "B", "M"], key=m['id'], horizontal=True, index=default_index)
            
            if st.button(f"Kaydet: {m['teams']}"):
                supabase.table("predictions").upsert({
                    "match_id": m['id'], "user_name": user, "prediction": choice
                }).execute()
                st.success(f"Tahmin kaydedildi: {choice}")
        else:
            st.error("🚫 Maça 30 dakikadan az kaldığı için tahmin yapılamaz.")
            
# --- 3. ADMIN (MAÇ EKLEME, DÜZENLEME VE SONUÇLANDIRMA) ---
elif menu == "⚽ Maç Ekle/Sonuçlandır":
    st.header("⚙️ Admin Paneli")
    
    # SEKME SİSTEMİYLE DAHA DÜZENLİ HALE GETİRDİK
    tab1, tab2, tab3 = st.tabs(["➕ Yeni Maç Ekle", "✏️ Maç Düzenle / Oran Güncelle", "✅ Sonuç Gir"])

    with tab1:
        st.subheader("Yeni Maç Bilgilerini Gir")
        t1 = st.text_input("Ev Sahibi")
        t2 = st.text_input("Deplasman")
        c1, c2, c3 = st.columns(3)
        og = c1.number_input("G Oranı", 1.0, key="new_g")
        ob = c2.number_input("B Oranı", 1.0, key="new_b")
        om = c3.number_input("M Oranı", 1.0, key="new_m")
        dt = st.date_input("Tarih", key="new_date")
        tm = st.time_input("Saat", key="new_time")
        
        if st.button("Maçı Sisteme Ekle"):
            full_dt = datetime.combine(dt, tm).isoformat()
            supabase.table("matches").insert({
                "teams": f"{t1} - {t2}", "odds_g": og, "odds_b": ob, "odds_m": om, "match_time": full_dt
            }).execute()
            st.success("Maç başarıyla eklendi!")

    with tab2:
        st.subheader("Mevcut Maçı Güncelle")
        # Henüz sonucu girilmemiş maçları çek
        editable_matches = supabase.table("matches").select("*").filter("result", "is", "null").execute().data
        
        if editable_matches:
            m_options = {m['teams']: m for m in editable_matches}
            selected_teams = st.selectbox("Düzenlenecek Maçı Seç", list(m_options.keys()))
            m_data = m_options[selected_teams]
            
            st.info(f"Seçili Maç ID: {m_data['id']} | Mevcut Oranlar: G:{m_data['odds_g']} B:{m_data['odds_b']} M:{m_data['odds_m']}")
            
            col1, col2, col3 = st.columns(3)
            new_og = col1.number_input("Yeni G Oranı", value=float(m_data['odds_g']), key="edit_g")
            new_ob = col2.number_input("Yeni B Oranı", value=float(m_data['odds_b']), key="edit_b")
            new_om = col3.number_input("Yeni M Oranı", value=float(m_data['odds_m']), key="edit_m")
            
            new_date = st.date_input("Yeni Tarih", value=datetime.fromisoformat(m_data['match_time']).date(), key="edit_date")
            new_time = st.time_input("Yeni Saat", value=datetime.fromisoformat(m_data['match_time']).time(), key="edit_time")
            
            if st.button("Değişiklikleri Kaydet"):
                new_full_dt = datetime.combine(new_date, new_time).isoformat()
                supabase.table("matches").update({
                    "odds_g": new_og, 
                    "odds_b": new_ob, 
                    "odds_m": new_om,
                    "match_time": new_full_dt
                }).eq("id", m_data['id']).execute()
                st.success("Maç bilgileri ve oranlar güncellendi!")
                st.rerun() # Sayfayı yenileyerek güncel bilgileri gösterir
        else:
            st.write("Düzenlenecek aktif maç bulunamadı.")

    with tab3:
        st.subheader("Maç Sonucu Onayla")
        pending_matches = supabase.table("matches").select("*").filter("result", "is", "null").execute().data
        if pending_matches:
            m_list = {m['teams']: m['id'] for m in pending_matches}
            selected_m = st.selectbox("Sonuçlandırmak İstediğiniz Maç", list(m_list.keys()))
            res = st.radio("Final Sonucu (90 Dakika)", ["G", "B", "M"], horizontal=True)
            
            if st.button("Sonucu Onayla ve Puanları Kilitle"):
                supabase.table("matches").update({"result": res}).eq("id", m_list[selected_m]).execute()
                st.success(f"{selected_m} maçı {res} olarak tescil edildi!")
                st.rerun()
        else:
            st.write("Bekleyen maç yok.")
