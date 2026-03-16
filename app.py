import streamlit as st
import requests
import msgpack
import os
import time

# --- 網頁外觀設定 ---
st.set_page_config(page_title="FF14 繁中服市場分析機", page_icon="💰", layout="wide")
st.title("🌟 FF14 繁中服市場分析機")

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

# --- 查價功能 ---
def get_lowest_price_info(item_id, dc_name):
    url = f"https://universalis.app/api/v2/{dc_name}/{item_id}?listings=1"
    try:
        res = requests.get(url).json()
        if 'listings' in res and len(res['listings']) > 0:
            best = res['listings'][0]
            world = best.get('worldName', '本服')
            return best['pricePerUnit'], world
        return 0, "無貨"
    except:
        return 0, "錯誤"

tab1, tab2 = st.tabs(["🔍 單品深度分析 (跨服比價)", "📈 市場海選排行榜 (批次掃描)"])

# === 分頁一：單品分析 ===
with tab1:
    st.markdown("### 🔍 裝備深度健檢與起源雷達")
    col_in1, col_in2 = st.columns([1, 3])
    with col_in1:
        selected_dc = st.selectbox("🌐 選擇大區：", ["陸行鳥", "莫古力", "貓區", "豆豆柴"], key="s_dc")
    with col_in2:
        single_item_input = st.text_input("📦 輸入單一物品名稱：", "雨衣")
        
    if st.button("單品分析啟動 🚀", type="primary"):
        if single_item_input not in name_to_item_id:
            st.error(f"❌ 找不到【{single_item_input}】")
        else:
            item_id = name_to_item_id[single_item_input]
            try:
                item_url = f"https://xivapi.com/Item/{item_id}"
                item_res = requests.get(item_url).json()
                links = item_res.get('GameContentLinks', {})
                
                # 檢查是否有配方
                recipes = links.get('Recipe', {}).get('ItemResult', [])
                if not isinstance(recipes, list): recipes = [recipes]
                
                if not recipes:
                    st.warning("⚠️ 此物品不可製作")
                    source_msgs = []
                    if 'GilShopItem' in links: source_msgs.append("💰 NPC 商店")
                    if 'SpecialShop' in links: source_msgs.append("🔄 特殊商店/兌換")
                    if 'InstanceContent' in links: source_msgs.append("⚔️ 副本掉落")
                    if 'Achievement' in links: source_msgs.append("🏆 成就獎勵")
                    if source_msgs:
                        st.info("📡 來源偵測：" + "、".join(source_msgs))
                        
                    price, world = get_lowest_price_info(item_id, selected_dc)
                    if price > 0:
                        st.success(f"💡 交易板最低售價：{price} G (位於 {world})")
                    else:
                        st.error("📉 目前交易板上無人販售。")
                else:
                    # 製作邏輯
                    recipe_id = recipes[0]
                    recipe_url = f"https://xivapi.com/Recipe/{recipe_id}"
                    r_data = requests.get(recipe_url).json()
                    
                    ingredients = []
                    for i in range(10):
                        ing = r_data.get(f"ItemIngredient{i}")
                        if ing:
                            ing_id = ing['ID']
                            ingredients.append({
                                "id": ing_id, 
                                "name": item_id_to_name.get(ing_id, ing['Name']), 
                                "amt": r_data.get(f"AmountIngredient{i}")
                            })
                    
                    with st.spinner("🛒 正在計算市場行情..."):
                        price, world = get_lowest_price_info(item_id, selected_dc)
                        total_cost = 0
                        details = []
                        for ing in ingredients:
                            p, w = get_lowest_price_info(ing['id'], selected_dc)
                            cost = p * ing['amt']
                            total_cost += cost
                            details.append({"材料名稱": ing['name'], "需求數量": ing['amt'], "最低單價": p, "🛒 最便宜": w})
                        
                        profit = price - total_cost
                    
                    st.markdown("---")
                    # 👇 恢復消失的大數字面板 👇
                    m1, m2, m3 = st.columns(3)
                    m1.metric(f"成品最低售價 ({world})", f"{price} G")
                    m2.metric("材料總成本", f"{total_cost} G")
                    m3.metric("✨ 預期淨利潤", f"{profit} G", delta=f"{profit} G")
                    
                    st.markdown("#### 📝 製作材料採購清單")
                    st.dataframe(details, use_container_width=True)
            except Exception as e:
                st.error(f"❌ 查價失敗：{e}")

# === 分頁二：排行榜 ===
with tab2:
    st.markdown("### 📈 批次掃描排行榜")
    with st.form("batch_form"):
        batch_dc = st.selectbox("🌐 選擇大區：", ["陸行鳥", "莫古力", "貓區", "豆豆柴"], key="b_dc")
        user_input = st.text_area("📋 請輸入清單 (每一行一個)：", "雨衣\n顯貴短上衣\n古典大劍", height=150)
        submitted = st.form_submit_button("批次分析啟動 🚀")

    if submitted:
        items = [i.strip() for i in user_input.split('\n') if i.strip()]
        leaderboard = []
        pb = st.progress(0)
        for idx, name in enumerate(items):
            if name in name_to_item_id:
                iid = name_to_item_id[name]
                p, _ = get_lowest_price_info(iid, batch_dc)
                leaderboard.append({"物品": name, "最低售價": p})
            pb.progress((idx + 1) / len(items))
        
        if leaderboard:
            st.success("🎉 掃描完成！")
            st.dataframe(leaderboard, use_container_width=True)
