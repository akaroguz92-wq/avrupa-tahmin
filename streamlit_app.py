import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime, date, time
from zoneinfo import ZoneInfo


# ============================================================
# AYARLAR
# ============================================================

st.set_page_config(
    page_title="Avrupa Maç Tahmin Yarışması",
    page_icon="🏆",
    layout="wide"
)

# ------------------------------------------------------------
# SUPABASE
# ------------------------------------------------------------
# Streamlit Cloud'da Secrets bölümüne:
#
# SUPABASE_URL = "https://....supabase.co"
# SUPABASE_KEY = "sb_publishable_..."
# ADMIN_PASSWORD = "..."
#
# eklemen önerilir.
# ------------------------------------------------------------

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    st.error(
        """
        ⚠️ Streamlit Secrets ayarları bulunamadı.

        Streamlit Cloud:
        Manage app → Settings → Secrets

        aşağıdaki bilgileri eklemelisin:

        SUPABASE_URL = "https://xxxxx.supabase.co"
        SUPABASE_KEY = "sb_publishable_xxxxx"
        ADMIN_PASSWORD = "admin_sifren"
        """
    )
    st.stop()


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# Türkiye saati
TR_TZ = ZoneInfo("Europe/Istanbul")

PLAYERS = [
    "Oğuz",
    "Recep",
    "Semih",
    "İbo"
]

RESULTS = [
    "G",
    "B",
    "M"
]


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def normalize_result(value):
    """
    G / B / M değerini standart hale getirir.
    """
    if value is None:
        return None

    value = str(value).strip().upper()

    if value in ["G", "B", "M"]:
        return value

    return None


def parse_match_time(value):
    """
    Supabase'den gelen tarih/saat bilgisini
    Europe/Istanbul timezone'ına çevirir.
    """

    if not value:
        return None

    try:
        # Supabase bazen Z gönderir
        value = str(value).replace("Z", "+00:00")

        dt = datetime.fromisoformat(value)

        # Eğer timezone bilgisi yoksa Türkiye saati kabul et
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TR_TZ)
        else:
            dt = dt.astimezone(TR_TZ)

        return dt

    except Exception:
        return None


def format_match_time(value):
    """
    Tarihi kullanıcıya Türkiye saatinde gösterir.
    """

    dt = parse_match_time(value)

    if dt is None:
        return "Tarih okunamadı"

    return dt.strftime("%d.%m.%Y %H:%M")


def calculate_points(prediction, result, odds):
    """
    Doğru tahmin:
    Puan = Oran x 10
    Maksimum = 50

    Yanlış tahmin = 0
    """

    prediction = normalize_result(prediction)
    result = normalize_result(result)

    if not prediction or not result:
        return 0.0

    if prediction != result:
        return 0.0

    odds_value = odds.get(result, 0)

    try:
        odds_value = float(odds_value)
    except Exception:
        odds_value = 0

    return min(odds_value * 10, 50.0)


def get_odds_map(match):
    """
    Maç oranlarını G/B/M formatına çevirir.
    """

    return {
        "G": float(match.get("odds_g") or 0),
        "B": float(match.get("odds_b") or 0),
        "M": float(match.get("odds_m") or 0)
    }


def get_active_matches():
    """
    Sonucu girilmemiş maçları getirir.
    """

    response = (
        supabase
        .table("matches")
        .select("*")
        .is_("result", "null")
        .order("match_time")
        .execute()
    )

    return response.data or []


def get_all_matches():
    """
    Tüm maçları getirir.
    """

    response = (
        supabase
        .table("matches")
        .select("*")
        .order("match_time")
        .execute()
    )

    return response.data or []


def get_all_predictions():
    """
    Tüm tahminleri getirir.
    """

    response = (
        supabase
        .table("predictions")
        .select("*")
        .execute()
    )

    return response.data or []


def get_existing_prediction(match_id, user_name):
    """
    Aynı oyuncunun aynı maç için mevcut tahminini bulur.
    """

    response = (
        supabase
        .table("predictions")
        .select("*")
        .eq("match_id", match_id)
        .eq("user_name", user_name)
        .limit(1)
        .execute()
    )

    data = response.data or []

    if data:
        return data[0]

    return None


def save_prediction(match_id, user_name, prediction):
    """
    Tahmin zaten varsa UPDATE,
    yoksa INSERT yapılır.

    Böylece upsert() kullanılmaz.
    """

    existing = get_existing_prediction(
        match_id,
        user_name
    )

    if existing:

        (
            supabase
            .table("predictions")
            .update({
                "prediction": prediction
            })
            .eq("id", existing["id"])
            .execute()
        )

        return "updated"

    else:

        (
            supabase
            .table("predictions")
            .insert({
                "match_id": match_id,
                "user_name": user_name,
                "prediction": prediction
            })
            .execute()
        )

        return "inserted"


def admin_authenticated():
    """
    Admin giriş kontrolü.
    """

    if st.session_state.get("admin_authenticated", False):
        return True

    st.warning("🔐 Admin işlemleri için giriş yapmalısınız.")

    password = st.text_input(
        "Admin Şifresi",
        type="password",
        key="admin_password"
    )

    if st.button(
        "🔓 Admin Girişi",
        key="admin_login"
    ):

        if password == ADMIN_PASSWORD:
            st.session_state.admin_authenticated = True
            st.success("Admin girişi başarılı.")
            st.rerun()

        else:
            st.error("❌ Hatalı admin şifresi.")

    return False


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🏆 Avrupa Tahmin Yarışması")

menu = st.sidebar.radio(
    "Menü",
    [
        "📊 Puan Durumu",
        "📝 Tahmin Yap",
        "⚽ Maç Yönetimi"
    ]
)

st.sidebar.divider()

user = st.sidebar.selectbox(
    "👤 Oyuncu",
    PLAYERS
)


# ============================================================
# 1. PUAN DURUMU
# ============================================================

if menu == "📊 Puan Durumu":

    st.header("📊 Genel Puan Durumu")

    try:

        matches = get_all_matches()
        predictions = get_all_predictions()

    except Exception as e:

        st.error("❌ Veriler alınamadı.")
        st.exception(e)
        st.stop()

    stats = []

    for player in PLAYERS:

        player_predictions = [
            p for p in predictions
            if p.get("user_name") == player
        ]

        total_points = 0.0
        correct_count = 0
        high_odds_count = 0
        max_single = 0.0
        prediction_count = 0

        for prediction in player_predictions:

            match = next(
                (
                    m for m in matches
                    if m.get("id") == prediction.get("match_id")
                ),
                None
            )

            if not match:
                continue

            result = normalize_result(
                match.get("result")
            )

            # Sadece sonuçlandırılmış maçlar puanlanır
            if not result:
                continue

            prediction_count += 1

            odds = get_odds_map(match)

            points = calculate_points(
                prediction.get("prediction"),
                result,
                odds
            )

            if points > 0:

                total_points += points
                correct_count += 1

                max_single = max(
                    max_single,
                    points
                )

                if odds[result] >= 3.00:
                    high_odds_count += 1

        stats.append({
            "Oyuncu": player,
            "Toplam Puan": round(total_points, 2),
            "Doğru": correct_count,
            "Tahmin Sayısı": prediction_count,
            "3.00+ Oran Bilme": high_odds_count,
            "En Yüksek Tek Maç": round(max_single, 2)
        })

    df = pd.DataFrame(stats)

    # --------------------------------------------------------
    # EŞİTLİK BOZMA
    # --------------------------------------------------------

    df = df.sort_values(
        by=[
            "Toplam Puan",
            "Doğru",
            "3.00+ Oran Bilme",
            "En Yüksek Tek Maç"
        ],
        ascending=False
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # DURUM
    # --------------------------------------------------------

    status = []

    for i in range(len(df)):

        if i == 0:
            status.append("💰 Kazanan (1.)")

        elif i == 1:
            status.append("💰 Kazanan (2.)")

        else:
            status.append("🍴 Ismarlıyor")

    df["Durum"] = status

    # --------------------------------------------------------
    # GÖSTERİM
    # --------------------------------------------------------

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    st.info(
        """
        💡 **Puanlama Sistemi**

        Doğru tahmin = Oran × 10

        Maksimum tek maç puanı = 50

        Yanlış tahmin = 0
        """
    )

    # --------------------------------------------------------
    # DETAY
    # --------------------------------------------------------

    st.subheader("📋 Maç Bazında Sonuçlar")

    finished_matches = [
        m for m in matches
        if normalize_result(m.get("result"))
    ]

    if not finished_matches:

        st.info("Henüz sonuçlandırılmış maç bulunmuyor.")

    else:

        detail_rows = []

        for match in finished_matches:

            result = normalize_result(
                match.get("result")
            )

            odds = get_odds_map(match)

            row = {
                "Maç": match.get("teams"),
                "Sonuç": result
            }

            for player in PLAYERS:

                prediction = next(
                    (
                        p for p in predictions
                        if p.get("match_id") == match.get("id")
                        and p.get("user_name") == player
                    ),
                    None
                )

                if prediction:

                    pred = normalize_result(
                        prediction.get("prediction")
                    )

                    points = calculate_points(
                        pred,
                        result,
                        odds
                    )

                    row[player] = (
                        f"{pred} → {points:.1f} puan"
                    )

                else:

                    row[player] = "Tahmin yok"

            detail_rows.append(row)

        st.dataframe(
            pd.DataFrame(detail_rows),
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# 2. TAHMİN YAP
# ============================================================

elif menu == "📝 Tahmin Yap":

    st.header("📝 Maç Tahminlerini Gir")

    try:

        active_matches = get_active_matches()

    except Exception as e:

        st.error("❌ Aktif maçlar alınamadı.")
        st.exception(e)
        st.stop()

    if not active_matches:

        st.info(
            "⚽ Şu anda tahmin yapılabilecek maç bulunmamaktadır."
        )

    now = datetime.now(TR_TZ)

    for match in active_matches:

        match_id = match.get("id")
        teams = match.get("teams", "Bilinmeyen Maç")

        match_time = parse_match_time(
            match.get("match_time")
        )

        if match_time is None:

            st.error(
                f"❌ {teams} için maç tarihi okunamadı."
            )

            continue

        deadline = match_time.replace(
            second=0,
            microsecond=0
        )

        # Maçtan 30 dakika önce tahmin kapanır
        deadline = deadline.replace()  # güvenli kopya

        # datetime - timedelta
        from datetime import timedelta

        deadline = match_time - timedelta(
            minutes=30
        )

        st.subheader(f"⚽ {teams}")

        # ----------------------------------------------------
        # ORANLAR
        # ----------------------------------------------------

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "🏠 Galibiyet",
            f"{float(match.get('odds_g') or 0):.2f}"
        )

        c2.metric(
            "🤝 Beraberlik",
            f"{float(match.get('odds_b') or 0):.2f}"
        )

        c3.metric(
            "✈️ Mağlubiyet",
            f"{float(match.get('odds_m') or 0):.2f}"
        )

        st.write(
            f"📅 **Maç:** "
            f"{match_time.strftime('%d.%m.%Y %H:%M')}"
        )

        st.write(
            f"⏰ **Tahmin son saati:** "
            f"{deadline.strftime('%d.%m.%Y %H:%M')}"
        )

        # ----------------------------------------------------
        # KALAN SÜRE
        # ----------------------------------------------------

        if now < deadline:

            remaining = deadline - now

            hours = int(
                remaining.total_seconds() // 3600
            )

            minutes = int(
                (remaining.total_seconds() % 3600) // 60
            )

            st.info(
                f"⏳ Tahmin için kalan süre: "
                f"**{hours} saat {minutes} dakika**"
            )

            # ------------------------------------------------
            # MEVCUT TAHMİN
            # ------------------------------------------------

            try:

                existing = get_existing_prediction(
                    match_id,
                    user
                )

            except Exception as e:

                st.error(
                    "❌ Mevcut tahmin kontrol edilemedi."
                )

                st.exception(e)

                continue

            prediction_options = [
                "G",
                "B",
                "M"
            ]

            default_index = 0

            if existing:

                current_prediction = normalize_result(
                    existing.get("prediction")
                )

                if current_prediction in prediction_options:

                    default_index = prediction_options.index(
                        current_prediction
                    )

                    st.success(
                        f"✅ Mevcut tahmininiz: "
                        f"**{current_prediction}**"
                    )

            # ------------------------------------------------
            # TAHMİN
            # ------------------------------------------------

            choice = st.radio(
                "Tahmininiz",
                prediction_options,
                index=default_index,
                horizontal=True,
                key=f"prediction_{match_id}_{user}"
            )

            # Açıklama
            descriptions = {
                "G": "🏠 Ev sahibi kazanır",
                "B": "🤝 Beraberlik",
                "M": "✈️ Deplasman kazanır"
            }

            st.caption(
                descriptions[choice]
            )

            # ------------------------------------------------
            # KAYDET
            # ------------------------------------------------

            if st.button(
                f"💾 Tahmini Kaydet",
                key=f"save_{match_id}_{user}",
                use_container_width=True
            ):

                # Kaydetme anında tekrar kontrol
                # Böylece kullanıcı sayfayı açık bıraksa bile
                # 30 dk sınırı aşılırsa kayıt yapılmaz.

                current_now = datetime.now(TR_TZ)

                if current_now >= deadline:

                    st.error(
                        "🚫 Tahmin süresi dolmuştur. "
                        "Maçtan 30 dakika önce tahminler kapanır."
                    )

                    st.rerun()

                try:

                    operation = save_prediction(
                        match_id,
                        user,
                        choice
                    )

                    if operation == "updated":

                        st.success(
                            f"✅ Tahmininiz güncellendi: "
                            f"**{choice}**"
                        )

                    else:

                        st.success(
                            f"✅ Tahmininiz kaydedildi: "
                            f"**{choice}**"
                        )

                    st.rerun()

                except Exception as e:

                    st.error(
                        """
                        ❌ Tahmin kaydedilemedi.

                        Bunun nedeni Supabase RLS/policy ayarları,
                        tablo kolonları veya veritabanı yetkileri olabilir.
                        """
                    )

                    st.exception(e)

        else:

            st.error(
                "🔒 Tahminler kapanmıştır. "
                "Maça 30 dakikadan az kaldığı için "
                "bu maça tahmin yapılamaz."
            )

        st.divider()


# ============================================================
# 3. MAÇ YÖNETİMİ
# ============================================================

elif menu == "⚽ Maç Yönetimi":

    st.header("⚙️ Admin Paneli")

    # --------------------------------------------------------
    # ADMIN LOGIN
    # --------------------------------------------------------

    if not admin_authenticated():
        st.stop()

    # --------------------------------------------------------
    # ADMIN LOGOUT
    # --------------------------------------------------------

    if st.button(
        "🔒 Admin Çıkışı",
        key="admin_logout"
    ):

        st.session_state.admin_authenticated = False
        st.rerun()

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "➕ Yeni Maç",
            "✏️ Maç Düzenle",
            "✅ Sonuç Gir",
            "🗑️ Maç Sil"
        ]
    )


    # ========================================================
    # TAB 1 - YENİ MAÇ
    # ========================================================

    with tab1:

        st.subheader("➕ Yeni Maç Ekle")

        team1 = st.text_input(
            "Ev Sahibi",
            key="new_team1"
        )

        team2 = st.text_input(
            "Deplasman",
            key="new_team2"
        )

        st.write("### 📊 Maç Oranları")

        c1, c2, c3 = st.columns(3)

        odds_g = c1.number_input(
            "G Oranı",
            min_value=1.01,
            value=2.00,
            step=0.01,
            key="new_odds_g"
        )

        odds_b = c2.number_input(
            "B Oranı",
            min_value=1.01,
            value=3.50,
            step=0.01,
            key="new_odds_b"
        )

        odds_m = c3.number_input(
            "M Oranı",
            min_value=1.01,
            value=3.00,
            step=0.01,
            key="new_odds_m"
        )

        st.write("### 📅 Maç Zamanı")

        c1, c2 = st.columns(2)

        match_date = c1.date_input(
            "Tarih",
            value=date.today(),
            key="new_date"
        )

        match_time_input = c2.time_input(
            "Saat",
            value=time(20, 0),
            key="new_time"
        )

        if st.button(
            "➕ Maçı Sisteme Ekle",
            use_container_width=True
        ):

            if not team1.strip():

                st.error(
                    "Ev sahibi takım girilmelidir."
                )

            elif not team2.strip():

                st.error(
                    "Deplasman takımı girilmelidir."
                )

            else:

                try:

                    # Türkiye saatine göre oluştur
                    local_dt = datetime.combine(
                        match_date,
                        match_time_input
                    ).replace(
                        tzinfo=TR_TZ
                    )

                    (
                        supabase
                        .table("matches")
                        .insert({
                            "teams":
                                f"{team1.strip()} - {team2.strip()}",
                            "odds_g": odds_g,
                            "odds_b": odds_b,
                            "odds_m": odds_m,
                            "match_time":
                                local_dt.isoformat()
                        })
                        .execute()
                    )

                    st.success(
                        f"✅ {team1} - {team2} maçı eklendi."
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        "❌ Maç eklenemedi."
                    )

                    st.exception(e)


    # ========================================================
    # TAB 2 - MAÇ DÜZENLE
    # ========================================================

    with tab2:

        st.subheader("✏️ Maç / Oran Güncelle")

        try:

            editable_matches = get_active_matches()

        except Exception as e:

            st.error("❌ Maçlar alınamadı.")
            st.exception(e)
            editable_matches = []

        if not editable_matches:

            st.info(
                "Düzenlenecek aktif maç bulunmamaktadır."
            )

        else:

            match_dict = {
                m["teams"]: m
                for m in editable_matches
            }

            selected_team = st.selectbox(
                "Düzenlenecek maç",
                list(match_dict.keys()),
                key="edit_match"
            )

            selected_match = match_dict[
                selected_team
            ]

            st.info(
                f"Maç ID: {selected_match['id']} | "
                f"Mevcut Oranlar → "
                f"G: {selected_match['odds_g']} | "
                f"B: {selected_match['odds_b']} | "
                f"M: {selected_match['odds_m']}"
            )

            c1, c2, c3 = st.columns(3)

            edit_g = c1.number_input(
                "Yeni G Oranı",
                min_value=1.01,
                value=float(selected_match["odds_g"]),
                step=0.01,
                key=f"edit_g_{selected_match['id']}"
            )

            edit_b = c2.number_input(
                "Yeni B Oranı",
                min_value=1.01,
                value=float(selected_match["odds_b"]),
                step=0.01,
                key=f"edit_b_{selected_match['id']}"
            )

            edit_m = c3.number_input(
                "Yeni M Oranı",
                min_value=1.01,
                value=float(selected_match["odds_m"]),
                step=0.01,
                key=f"edit_m_{selected_match['id']}"
            )

            selected_dt = parse_match_time(
                selected_match["match_time"]
            )

            c1, c2 = st.columns(2)

            edit_date = c1.date_input(
                "Yeni Tarih",
                value=selected_dt.date(),
                key=f"edit_date_{selected_match['id']}"
            )

            edit_time = c2.time_input(
                "Yeni Saat",
                value=selected_dt.time(),
                key=f"edit_time_{selected_match['id']}"
            )

            if st.button(
                "💾 Değişiklikleri Kaydet",
                use_container_width=True
            ):

                try:

                    local_dt = datetime.combine(
                        edit_date,
                        edit_time
                    ).replace(
                        tzinfo=TR_TZ
                    )

                    (
                        supabase
                        .table("matches")
                        .update({
                            "odds_g": edit_g,
                            "odds_b": edit_b,
                            "odds_m": edit_m,
                            "match_time":
                                local_dt.isoformat()
                        })
                        .eq(
                            "id",
                            selected_match["id"]
                        )
                        .execute()
                    )

                    st.success(
                        "✅ Maç bilgileri güncellendi."
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        "❌ Güncelleme başarısız."
                    )

                    st.exception(e)


    # ========================================================
    # TAB 3 - SONUÇ
    # ========================================================

    with tab3:

        st.subheader("✅ Maç Sonucu Gir")

        try:

            pending_matches = get_active_matches()

        except Exception as e:

            st.error("❌ Maçlar alınamadı.")
            st.exception(e)
            pending_matches = []

        if not pending_matches:

            st.info(
                "Sonuç girilecek maç bulunmamaktadır."
            )

        else:

            match_dict = {
                m["teams"]: m
                for m in pending_matches
            }

            selected_team = st.selectbox(
                "Sonuçlandırılacak maç",
                list(match_dict.keys()),
                key="result_match"
            )

            result_match = match_dict[
                selected_team
            ]

            st.write(
                f"⚽ **{result_match['teams']}**"
            )

            result = st.radio(
                "90 Dakika Sonucu",
                [
                    "G",
                    "B",
                    "M"
                ],
                horizontal=True,
                key="final_result"
            )

            descriptions = {
                "G": "🏠 Ev sahibi kazandı",
                "B": "🤝 Maç berabere bitti",
                "M": "✈️ Deplasman kazandı"
            }

            st.info(
                descriptions[result]
            )

            st.warning(
                """
                ⚠️ Sonucu onayladığınızda maç kesinleşir ve
                ilgili tahminler üzerinden puanlar hesaplanır.
                """
            )

            if st.button(
                "✅ Sonucu Onayla ve Maçı Kilitle",
                use_container_width=True
            ):

                try:

                    (
                        supabase
                        .table("matches")
                        .update({
                            "result": result
                        })
                        .eq(
                            "id",
                            result_match["id"]
                        )
                        .execute()
                    )

                    st.success(
                        f"✅ {selected_team} maçı "
                        f"**{result}** olarak tescil edildi."
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        "❌ Sonuç kaydedilemedi."
                    )

                    st.exception(e)


    # ========================================================
    # TAB 4 - MAÇ SİL
    # ========================================================

    with tab4:

        st.subheader("🗑️ Maç Sil")

        try:

            all_matches = get_all_matches()

        except Exception as e:

            st.error("❌ Maçlar alınamadı.")
            st.exception(e)
            all_matches = []

        if not all_matches:

            st.info("Silinecek maç bulunmamaktadır.")

        else:

            delete_dict = {
                m["teams"]: m
                for m in all_matches
            }

            delete_team = st.selectbox(
                "Silinecek maç",
                list(delete_dict.keys()),
                key="delete_match"
            )

            delete_match = delete_dict[
                delete_team
            ]

            st.warning(
                f"⚠️ **{delete_team}** maçı silinecek."
            )

            confirm_delete = st.checkbox(
                "Bu maçı silmek istediğimi onaylıyorum."
            )

            if st.button(
                "🗑️ Maçı Sil",
                disabled=not confirm_delete,
                use_container_width=True
            ):

                try:

                    # Önce tahminleri sil
                    (
                        supabase
                        .table("predictions")
                        .delete()
                        .eq(
                            "match_id",
                            delete_match["id"]
                        )
                        .execute()
                    )

                    # Daha sonra maçı sil
                    (
                        supabase
                        .table("matches")
                        .delete()
                        .eq(
                            "id",
                            delete_match["id"]
                        )
                        .execute()
                    )

                    st.success(
                        f"✅ {delete_team} maçı silindi."
                    )

                    st.rerun()

                except Exception as e:

                    st.error(
                        "❌ Maç silinemedi."
                    )

                    st.exception(e)


# ============================================================
# ALT BİLGİ
# ============================================================

st.sidebar.divider()

st.sidebar.caption(
    "🏆 Avrupa Maç Tahmin Yarışması"
)

st.sidebar.caption(
    "Puan = Doğru Tahmin × Oran × 10"
)
