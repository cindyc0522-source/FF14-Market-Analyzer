import streamlit as st
import requests
import msgpack
import os
import time

# --- 網頁外觀設定 ---
st.set_page_config(page_title="FF14 繁中服大亨", page_icon="💰", layout="wide")
st.title("🌟 FF14 繁中服市場分析機 (視覺增強版)")

# --- 載入資料庫 ---
@st.cache_data
def load_data():
    file_name = "tw-items.msgpack"
    if not os.path.exists(file_name):
        url = "https://beherw.github.io/FFXIV_Market/data/tw-items.msgpack"
        res = requests.get(url)
        with open(file_name, 'wb') as f:
            f.write(res.content)
    with open(file_name, 'rb') as f:
        raw_data = msgpack.unpackb(f.read(), strict_map_key=False)
    name_to_id = {}
    id_to_name = {}
    for item_id_str, item_info in raw_data.items():
        if type(item_info) is dict and 'tw' in item_info:
            tw_name = item_info['tw']
            num_id = int(item_id_str)
            name_to_id[tw_name] = num_id
            id_to_name[num_id] = tw_name
    return name_to_id, id_to_name

name_to_item_id, item_id_to_name = load_data()
all_item_names = list(name_to_item_id.keys())

# --- 輔助功能：計算圖標網址 ---
def get_icon_url(item_id):
    # FF14 圖標網址邏輯：ID 補足 6 位數，前 3 位加 000 作為資料夾
    item_id_str = str(item_id).zfill(6)
    folder = item_id_str[:3] + "000"
    return f"https://xivapi.com/i/{folder}/{item_id_str}.png"

# --- 查價功能 ---
def get_lowest_price_info(item_id, dc_name):
    url = f"https://universalis.app/api/v2/{dc_name}/{item_id}?listings=1"
    try:
        res = requests.get(url).json()
        if 'listings' in res and len(res['listings']) > 0:
            best = res['listings'][0]
            return best['pricePerUnit'], best.get('worldName', '未知')
    except: pass
    return 0, "無貨"

tab1, tab2 = st.tabs(["🔍 智慧搜尋與深度分析", "📈 批次快速排行榜"])

# === 分頁一：視覺化搜尋 ===
with tab1:
    st.markdown("### 📦 道具關鍵字搜尋")
    col_a, col_b = st.columns([1, 2])
    
    with col_a:
        dc = st.selectbox("🌐 選擇大區：", ["陸行鳥", "莫古力", "貓區", "豆豆柴"], key="s_dc")
        keyword = st.text_input("📝 請輸入關鍵字：", "雨衣")
    
    # 模糊搜尋
    matches = [name for name in all_item_names if keyword in name][:15] # 限制前15個，效能較好
    
    if keyword and matches:
        search_results = []
        for m_name in matches:
            m_id = name_to_item_id[m_name]
            search_results.append({
                "圖標": get_icon_url(m_id),
                "物品名稱": m_name,
                "ID": m_id
            })
        
        with col_b:
            st.write(f"📡 找到 {len(matches)} 個匹配項：")
            # 👇 這裡就是帶圖片的表格設定 👇
            st.dataframe(
                search_results,
                column_config={
                    "圖標": st.column_config.ImageColumn("圖標", help="道具圖示"),
                    "物品名稱": st.column_config.TextColumn("名稱"),
                },
                use_container_width=True,
                hide_index=True
            )
            
        st.markdown("---")
        target_item = st.selectbox("🎯 請從上方結果選擇一個進行深度分析：", matches)
        
        if st.button("查看詳細報報 🚀", type="primary"):
            tid = name_to_item_id[target_item]
            try:
                # 取得配方與來源
                i_res = requests.get(f"https://xivapi.com/Item/{tid}").json()
                links = i_res.get('GameContentLinks', {})
                recipes = links.get('Recipe', {}).get('ItemResult', [])
                if not isinstance(recipes, list): recipes = [recipes]
                
                if not recipes:
                    st.warning("此物品不可製作，來源雷達：")
                    msgs = []
                    if 'GilShopItem' in links: msgs.append("💰 商店販售")
                    if 'SpecialShop' in links: msgs.append("🔄 兌換/特殊商店")
                    if 'InstanceContent' in links: msgs.append("⚔️ 副本掉落")
                    st.info("、".join(msgs) if msgs else "未知來源")
                    
                    p, w = get_lowest_price_info(tid, dc)
                    st.success(f"市場最低價：{p} G (伺服器：{w})")
                else:
                    # 製作分析
                    r_res = requests.get(f"https://xivapi.com/Recipe/{recipes[0]}").json()
                    mats = []
                    cost = 0
                    for i in range(10):
                        ing = r_res.get(f"ItemIngredient{i}")
                        if ing:
                            iid = ing['ID']
                            amt = r_res.get(f"AmountIngredient{i}")
                            p, w = get_lowest_price_info(iid, dc)
                            cost += p * amt
                            mats.append({
                                "圖標": get_icon_url(iid),
                                "材料名稱": item_id_to_name.get(iid, ing['Name']),
                                "數量": amt,
                                "單價": p,
                                "總計": p * amt,
                                "推薦購買": w
                            })
                    
                    price, world = get_lowest_price_info(tid, dc)
                    m1, m2, m3 = st.columns(3)
                    m1.metric(f"成品售價 ({world})", f"{price} G")
                    m2.metric("材料總成本", f"{cost} G")
                    m3.metric("預期利潤", f"{price - cost} G", delta=f"{price - cost} G")
                    
                    st.dataframe(
                        mats,
                        column_config={"圖標": st.column_config.ImageColumn()},
                        use_container_width=True,
                        hide_index=True
                    )
            except:
                st.error("API 連線繁忙，請再試一次。")
    elif keyword:
        st.error("找不到任何道具。")

# === 分頁二：快速掃描 ===
with tab2:
    st.markdown("### 📈 快速批次查價")
    with st.form("b_form"):
        bdc = st.selectbox("大區", ["陸行鳥", "莫古力", "貓區", "豆豆柴"])
        txt = st.text_area("清單：", "雨衣\n顯貴短上衣", height=150)
        if st.form_submit_button("批次查價"):
            items = [i.strip() for i in txt.split('\n') if i.strip()]
            res = []
            for n in items:
                if n in name_to_item_id:
                    iid = name_to_item_id[n]
                    p, w = get_lowest_price_info(iid, bdc)
                    res.append({"圖標": get_icon_url(iid), "名稱": n, "價格": p, "伺服器": w})
            st.dataframe(res, column_config={"圖標": st.column_config.ImageColumn()}, use_container_width=True)
