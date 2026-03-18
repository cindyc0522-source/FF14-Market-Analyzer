import streamlit as st
import requests
import msgpack
import os
import zhconv

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
    id_to_cn_name = {}

    for item_id_str, item_info in raw_data.items():
        if isinstance(item_info, dict) and 'tw' in item_info:
            tw_name = item_info['tw']
            num_id = int(item_id_str)
            name_to_id[tw_name] = num_id
            id_to_name[num_id] = tw_name
            
            cn_name = item_info.get('cn') or item_info.get('chs') or item_info.get('zh')
            if cn_name:
                id_to_cn_name[num_id] = cn_name
                
    return name_to_id, id_to_name, id_to_cn_name

name_to_item_id, item_id_to_name, id_to_cn_name = load_data()
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
        keyword = st.text_input("📝 輸入關鍵字：", "古典大劍") # 換成一個有很多半成品的裝備來測試

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
            cn_api_url = f"https://cafemaker.wakingsands.com/Item/{item_id}?columns=Name"
            cn_res = requests.get(cn_api_url, timeout=3).json()
            official_cn_name = cn_res.get("Name")
        except:
            official_cn_name = None

        if official_cn_name:
            cn_target_item = official_cn_name
        else:
            cn_target_item = zhconv.convert(target_item, 'zh-cn')

        try:
            item_res = requests.get(f"https://xivapi.com/Item/{item_id}").json()
            links = item_res.get('GameContentLinks', {})
            recipes = links.get('Recipe', {}).get('ItemResult', [])
            
            icon_path = item_res.get('Icon')
            icon_html = f"<img src='https://xivapi.com{icon_path}' width='36' style='vertical-align: middle; border-radius: 6px; margin-right: 8px;'>" if icon_path else ""

            st.markdown(f"#### {icon_html}📚 【{target_item}】詳細資訊", unsafe_allow_html=True)
            col_w1, col_w2 = st.columns(2)
            with col_w1:
                st.link_button(f"📖 前往【灰機 Wiki】查看中文攻略", f"https://ff14.huijiwiki.com/wiki/物品:{cn_target_item}", use_container_width=True)
            with col_w2:
                st.link_button("🧰 前往【Garland Tools】查看地圖", f"https://www.garlandtools.org/db/#item/{item_id}", use_container_width=True)
            
            st.markdown("---")

            if not isinstance(recipes, list):
                recipes = [recipes]

            # ===== 不可製作 =====
            if not recipes:
                st.warning(f"⚠️ 這是不可製作物品！")
                
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
                
                job_id = r_data.get("ClassJob", {}).get("ID")
                job_name = JOB_MAP.get(job_id, "未知職業")
                base_level = r_data.get("RecipeLevelTable", {}).get("ClassJobLevel", "?")
                stars = r_data.get("RecipeLevelTable", {}).get("Stars", 0)
                star_str = "★" * stars if stars > 0 else ""
                
                st.success(f"🛠️ **製作條件：** {job_name} Lv.{base_level} {star_str}")

                ingredients = []
                for i in range(10):
                    ing = r_data.get(f"ItemIngredient{i}")
                    if ing:
                        iid = ing['ID']
                        ing_icon = f"https://xivapi.com{ing['Icon']}" if 'Icon' in ing else None
                        ingredients.append({
                            "id": iid,
                            "name": item_id_to_name.get(iid, ing['Name']),
                            "amt": r_data.get(f"AmountIngredient{i}"),
                            "icon": ing_icon,
                            "lowest_price": 0,
                            "sub_details": [],
                            "sub_total_cost": 0,
                            "is_craftable": False
                        })

                # ⚠️ 因為要進行第二層深度掃描，這會多花幾秒鐘
                with st.spinner("🛒 深入解析素材來源、半成品配方與市場價格中...(約需5~10秒)"):
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
                        # 1. 抓市場價格
                        ing_market = get_market_listings(ing['id'], selected_dc, 3)
                        if ing_market:
                            lowest_price = ing_market[0]["單價"]
                            ing['lowest_price'] = lowest_price
                            total_cost += lowest_price * ing['amt']
                            market_text = " / ".join([f"{m['單價']}×{m['數量']}({short_world(m['世界'])})" for m in ing_market])
                        else:
                            market_text = "無"

                        # 2. 抓素材取得管道 & 判斷是否為半成品
                        ing_source_text = "❓ 未知"
                        try:
                            ing_item_res = requests.get(f"https://xivapi.com/Item/{ing['id']}").json()
                            i_links = ing_item_res.get('GameContentLinks', {})
                            i_sources = []
                            if 'GilShopItem' in i_links: i_sources.append("💰 NPC")
                            if 'GatheringItem' in i_links: i_sources.append("⛏️ 採集")
                            
                            # ✨ 判斷是否可以製作 (抓出子配方)
                            sub_recipes_ids = i_links.get('Recipe', {}).get('ItemResult', [])
                            if sub_recipes_ids:
                                i_sources.append("🛠️ 製作")
                                ing['is_craftable'] = True
                                if not isinstance(sub_recipes_ids, list):
                                    sub_recipes_ids = [sub_recipes_ids]
                                
                                # ✨ 第二層深度掃描：抓取半成品的配方和底層材料價格
                                sub_r_data = requests.get(f"https://xivapi.com/Recipe/{sub_recipes_ids[0]}").json()
                                sub_output_amt = sub_r_data.get("AmountResult", 1) # 半成品一次搓幾個出來
                                
                                for j in range(10):
                                    sub_ing = sub_r_data.get(f"ItemIngredient{j}")
                                    if sub_ing:
                                        sub_iid = sub_ing['ID']
                                        sub_amt = sub_r_data.get(f"AmountIngredient{j}")
                                        sub_name = item_id_to_name.get(sub_iid, sub_ing['Name'])
                                        
                                        sub_market = get_market_listings(sub_iid, selected_dc, 1)
                                        if sub_market:
                                            sub_price = sub_market[0]["單價"]
                                            sub_world = short_world(sub_market[0]["世界"])
                                            ing['sub_total_cost'] += sub_price * sub_amt
                                            sub_market_text = f"{sub_price} G ({sub_world})"
                                        else:
                                            sub_market_text = "無"
                                            
                                        ing['sub_details'].append({
                                            "底層材料": sub_name,
                                            "單次需求": sub_amt,
                                            "最低單價": sub_market_text
                                        })
                                # 換算成單個半成品的成本
                                ing['sub_total_cost'] = int(ing['sub_total_cost'] / sub_output_amt)

                            ing_source_text = "、".join(i_sources) if i_sources else "❓ 未知"
                        except:
                            pass

                        details.append({
                            "圖示": ing['icon'],
                            "材料": ing['name'],
                            "需求": ing['amt'],
                            "取得管道": ing_source_text,
                            "市場前3筆": market_text,
                        })

                    profit = price - total_cost

                # === 頂部總結儀表板 ===
                c1, c2, c3 = st.columns(3)
                c1.metric("成品單價", f"{price} G ({short_world(world)})")
                c2.metric("材料全買成本", f"{total_cost} G")
                c3.metric("最低預期利潤", f"{profit} G")

                st.markdown("### 🧾 製作材料清單 (主配方)")
                st.dataframe(
                    details, 
                    use_container_width=True,
                    column_config={
                        "圖示": st.column_config.ImageColumn("圖示", width="small")
                    }
                )

                # ✨ 全新區塊：半成品自製 vs 購買 決策系統 ✨
                st.markdown("---")
                st.markdown("### 🛠️ 半成品評估：自製 vs 購買")
                has_sub_crafts = False
                
                for ing in ingredients:
                    if ing['is_craftable'] and ing['sub_details']:
                        has_sub_crafts = True
                        buy_price = ing['lowest_price']
                        craft_price = ing['sub_total_cost']
                        
                        if buy_price == 0:
                            status_msg = "⚠️ 市場缺貨，只能自己做！"
                        elif craft_price < buy_price:
                            status_msg = f"✅ 自己做更省 (省 {buy_price - craft_price} G)"
                        else:
                            status_msg = f"💰 直接買更省 (省 {craft_price - buy_price} G)"
                            
                        # 這就是你想要的「隱藏表格 (Expander)」
                        with st.expander(f"📦 {ing['name']} ｜ 市場單價: {buy_price} G ｜ 自製成本: {craft_price} G ➡️ {status_msg}"):
                            st.dataframe(ing['sub_details'], use_container_width=True, hide_index=True)
                            
                if not has_sub_crafts:
                    st.info("此配方沒有需要進一步製作的半成品素材，或底層資料庫讀取中。")

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
