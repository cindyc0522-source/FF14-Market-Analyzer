import streamlit as st
import requests
import msgpack
import os

# --- 網頁設定 ---
st.set_page_config(page_title="FF14 繁中服市場分析機", page_icon="💰", layout="wide")
st.title("🌟 FF14 繁中服市場分析機")

# --- 職業 ID 翻譯蒟蒻 ---
JOB_MAP = {
    8: "刻木匠", 9: "鍛鐵匠", 10: "鑄甲匠", 11: "雕金匠",
    12: "製革匠", 13: "裁衣匠", 14: "鍊金術士", 15: "烹調師"
}

# --- 世界名稱簡寫 ---
def short_world(name):
    return name.replace("幻影群島", "幻影").replace("莫古力", "莫古") \
               .replace("陸行鳥", "鳥").replace("豆豆柴", "柴").replace("貓小胖", "貓")

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
        if isinstance(item_info, dict) and 'tw' in item_info:
            tw_name = item_info['tw']
            num_id = int(item_id_str)
            name_to_id[tw_name] = num_id
            id_to_name[num_id] = tw_name
    return name_to_id, id_to_name

name_to_item_id, item_id_to_name = load_data()
all_item_names = list(name_to_item_id.keys())

# --- 查市場前N筆 ---
def get_market_listings(item_id, dc_name, limit=5):
    url = f"https://universalis.app/api/v2/{dc_name}/{item_id}?listings={limit}"
    try:
        res = requests.get(url).json()
        listings_data = []
        if 'listings' in res and len(res['listings']) > 0:
            for l in res['listings'][:limit]:
                listings_data.append({
                    "單價": l.get("pricePerUnit", 0),
                    "數量": l.get("quantity", 0),
                    "總價": l.get("pricePerUnit", 0) * l.get("quantity", 0),
                    "世界": l.get("worldName", "本服")
                })
        return listings_data
    except:
        return []

# --- 取得最低價 ---
def get_lowest_price(item_id, dc_name):
    data = get_market_listings(item_id, dc_name, limit=1)
    if data:
        return data[0]["單價"], data[0]["世界"]
    return 0, "無"

tab1, tab2 = st.tabs(["🔍 單品深度分析", "📈 市場海選排行榜"])

# =============================
# 分頁一
# =============================
with tab1:
    st.markdown("### 🔍 裝備關鍵字搜尋")
    col_s1, col_s2 = st.columns([1, 2])

    with col_s1:
        selected_dc = st.selectbox("🌐 選擇大區：", ["陸行鳥", "莫古力", "貓區", "豆豆柴"])
        keyword = st.text_input("📝 輸入關鍵字：", "雨衣")

    matches = [name for name in all_item_names if keyword in name]

    with col_s2:
        if keyword:
            if matches:
                target_item = st.selectbox(f"🎯 找到 {len(matches)} 個結果：", matches)
            else:
                st.error("❌ 找不到道具")
                target_item = None
        else:
            st.info("請輸入關鍵字")
            target_item = None

    if target_item and st.button("啟動分析 🚀"):
        item_id = name_to_item_id[target_item]

        try:
            item_res = requests.get(f"https://xivapi.com/Item/{item_id}").json()
            links = item_res.get('GameContentLinks', {})
            recipes = links.get('Recipe', {}).get('ItemResult', [])

            if not isinstance(recipes, list):
                recipes = [recipes]

            # ===== 不可製作 =====
            if not recipes:
                st.warning(f"⚠️ 【{target_item}】為不可製作物品！")
                
                # ✨ 新功能：透過反向連結推測來源 ✨
                sources = []
                if 'GilShopItem' in links: sources.append("💰 NPC 金幣商店販售")
                if 'SpecialShop' in links: sources.append("🎟️ 特殊代幣 / 神典石兌換")
                if 'InstanceContent' in links: sources.append("⚔️ 副本 / 討伐戰掉落")
                if 'GatheringItem' in links: sources.append("⛏️ 園藝 / 採礦取得")
                if 'FishParameter' in links or 'SpearfishingItem' in links: sources.append("🎣 釣魚 / 刺魚取得")
                if 'TreasureHuntRank' in links: sources.append("🗺️ 藏寶圖取得")
                
                source_text = "、".join(sources) if sources else "❓ 怪物掉落 / 任務獎勵 / 寶箱或未知來源"
                st.info(f"💡 **系統推測取得管道：** {source_text}")

                market = get_market_listings(item_id, selected_dc)
                if market:
                    st.markdown("### 💰 市場前5筆")
                    st.dataframe(market, use_container_width=True)
                else:
                    st.warning("無交易資料")

            # ===== 可製作 =====
            else:
                r_data = requests.get(f"https://xivapi.com/Recipe/{recipes[0]}").json()
                
                # ✨ 新功能：抓取職業與等級 ✨
                job_id = r_data.get("ClassJob", {}).get("ID")
                job_name = JOB_MAP.get(job_id, "未知職業")
                base_level = r_data.get("RecipeLevelTable", {}).get("ClassJobLevel", "?")
                stars = r_data.get("RecipeLevelTable", {}).get("Stars", 0)
                star_str = "★" * stars if stars > 0 else "" # 如果是高難度星級配方，自動加上星星
                
                st.success(f"🛠️ **製作條件：** {job_name} Lv.{base_level} {star_str}")

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

                with st.spinner("🛒 讀取市場中..."):
                    market = get_market_listings(item_id, selected_dc)
                    if market:
                        price = market[0]["單價"]
                        world = market[0]["世界"]
                    else:
                        price = 0
                        world = "無"

                    total_cost = 0
                    details = []

                    for ing in ingredients:
                        ing_market = get_market_listings(ing['id'], selected_dc, 3)
                        if ing_market:
                            lowest_price = ing_market[0]["單價"]
                            total_cost += lowest_price * ing['amt']
                            market_text = " / ".join([f"{m['單價']}×{m['數量']}({short_world(m['世界'])})" for m in ing_market])
                        else:
                            market_text = "無"

                        details.append({
                            "材料": ing['name'],
                            "需求": ing['amt'],
                            "市場前3筆": market_text
                        })

                    profit = price - total_cost

                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                c1.metric("成品單價", f"{price} G ({short_world(world)})")
                c2.metric("材料成本", f"{total_cost} G")
                c3.metric("預期利潤", f"{profit} G")

                st.markdown("### 💰 成品市場")
                if market:
                    st.dataframe(market, use_container_width=True)

                st.markdown("### 🧾 材料")
                st.caption("格式：單價×數量(世界)")
                st.dataframe(details, use_container_width=True)

        except Exception as e:
            st.error("API錯誤或網路不穩")

# =============================
# 分頁二
# =============================
with tab2:
    st.markdown("### 📈 批次掃描")
    with st.form("form"):
        dc = st.selectbox("大區", ["陸行鳥", "莫古力", "貓區", "豆豆柴"])
        text = st.text_area("輸入清單", "雨衣\n顯貴短上衣")
        if st.form_submit_button("掃描"):
            items = [i.strip() for i in text.split('\n') if i.strip()]
            result = []
            pb = st.progress(0)
            for i, name in enumerate(items):
                if name in name_to_item_id:
                    p, _ = get_lowest_price(name_to_item_id[name], dc)
                    result.append({"物品": name, "最低價": p})
                pb.progress((i + 1) / len(items))
            st.dataframe(result, use_container_width=True)
