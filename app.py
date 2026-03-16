import streamlit as st
import requests
import msgpack
import os
import time

# --- 網頁設定 ---
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
all_item_names = list(name_to_item_id.keys())

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

tab1, tab2 = st.tabs(["🔍 單品深度分析", "📈 市場海選排行榜"])

# === 分頁一：模糊搜尋與分析 ===
with tab1:
    st.markdown("### 🔍 裝備關鍵字搜尋")
    col_s1, col_s2 = st.columns([1, 2])
    
    with col_s1:
        selected_dc = st.selectbox("🌐 選擇大區：", ["陸行鳥", "莫古力", "貓區", "豆豆柴"], key="single_dc")
        keyword = st.text_input("📝 輸入關鍵字 (例如：短上衣)：", "雨衣")
    
    # 👇 模糊搜尋邏輯：找出所有包含關鍵字的名字 👇
    matches = [name for name in all_item_names if keyword in name]
    
    with col_s2:
        if keyword:
            if matches:
                target_item = st.selectbox(f"🎯 找到 {len(matches)} 個結果，請選擇：", matches)
            else:
                st.error("❌ 找不到包含該關鍵字的道具。")
                target_item = None
        else:
            st.info("請先在左側輸入關鍵字。")
            target_item = None

    if target_item and st.button("啟動深度分析 🚀", type="primary"):
        item_id = name_to_item_id[target_item]
        try:
            item_url = f"https://xivapi.com/Item/{item_id}"
            item_res = requests.get(item_url).json()
            links = item_res.get('GameContentLinks', {})
            
            # 檢查配方
            recipes = links.get('Recipe', {}).get('ItemResult', [])
            if not isinstance(recipes, list): recipes = [recipes]
            
            if not recipes:
                st.warning(f"⚠️ 【{target_item}】不可製作")
                source_msgs = []
                if 'GilShopItem' in links: source_msgs.append("💰 NPC 商店")
                if 'SpecialShop' in links: source_msgs.append("🔄 特殊商店/兌換")
                if 'InstanceContent' in links: source_msgs.append("⚔️ 副本掉落")
                if 'Achievement' in links: source_msgs.append("🏆 成就獎勵")
                if source_msgs: st.info("📡 來源偵測：" + "、".join(source_msgs))
                
                price, world = get_lowest_price_info(item_id, selected_dc)
                if price > 0: st.success(f"💡 交易板最低：{price} G ({world})")
            else:
                recipe_id = recipes[0]
                r_url = f"https://xivapi.com/Recipe/{recipe_id}"
                r_data = requests.get(r_url).json()
                
                ingredients = []
                for i in range(10):
                    ing = r_data.get(f"ItemIngredient{i}")
                    if ing:
                        iid = ing['ID']
                        ingredients.append({
                            "id": iid, 
                            "name": item_id_to_name.get(iid, ing['Name']), 
                            "amt": r_data.get(f"AmountIngredient{i}")
                        })
                
                with st.spinner("🛒 正在跑遍交易板..."):
                    price, world = get_lowest_price_info(item_id, selected_dc)
                    total_cost = 0
                    details = []
                    for ing in ingredients:
                        p, w = get_lowest_price_info(ing['id'], selected_dc)
                        total_cost += p * ing['amt']
                        details.append({"材料名稱": ing['name'], "數量": ing['amt'], "單價": p, "最便宜": w})
                    profit = price - total_cost

                st.markdown("---")
                m1, m2, m3 = st.columns(3)
                m1.metric(f"成品售價 ({world})", f"{price} G")
                m2.metric("材料成本", f"{total_cost} G")
                m3.metric("預期利潤", f"{profit} G", delta=f"{profit} G")
                st.dataframe(details, use_container_width=True)
        except:
            st.error("連線超時，請重試。")

# === 分頁二：排行榜 (維持原樣) ===
with tab2:
    st.markdown("### 📈 批次掃描排行榜")
    with st.form("b_form"):
        batch_dc = st.selectbox("🌐 選擇大區：", ["陸行鳥", "莫古力", "貓區", "豆豆柴"], key="b_dc")
        user_input = st.text_area("📋 清單：", "雨衣\n顯貴短上衣\n古典大劍", height=150)
        if st.form_submit_button("批次掃描 🚀"):
            items = [i.strip() for i in user_input.split('\n') if i.strip()]
            res = []
            pb = st.progress(0)
            for idx, name in enumerate(items):
                if name in name_to_item_id:
                    p, _ = get_lowest_price_info(name_to_item_id[name], batch_dc)
                    res.append({"物品": name, "最低售價": p})
                pb.progress((idx + 1) / len(items))
            st.dataframe(res, use_container_width=True)
