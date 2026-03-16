import streamlit as st
import requests
import msgpack
import os
import time

st.set_page_config(page_title="FF14 繁中服市場分析機", page_icon="💰", layout="wide")
st.title("🌟 FF14 繁中服市場分析機")

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

# === 分頁一：單品深度分析 ===
with tab1:
    st.markdown("### 🔍 裝備深度健檢與起源雷達")
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_dc = st.selectbox("🌐 選擇大區：", ["陸行鳥", "莫古力", "貓區", "豆豆柴"])
    with col2:
        single_item_input = st.text_input("📦 輸入單一物品名稱 (例如：雨衣、神兵戒指)：", "雨衣")
        
    if st.button("單品分析啟動 🚀", type="primary"):
        if single_item_input not in name_to_item_id:
            st.error(f"❌ 找不到【{single_item_input}】，請檢查錯字。")
        else:
            crafted_item_id = name_to_item_id[single_item_input]
            st.success(f"鎖定目標：【{single_item_input}】 (準備前往圖書館...)")
            
            try:
                item_url = f"https://xivapi.com/Item/{crafted_item_id}"
                item_res = requests.get(item_url).json()
                links = item_res.get('GameContentLinks')
                
                recipes_linked = []
                if links and 'Recipe' in links and 'ItemResult' in links['Recipe']:
                    recipes_linked = links['Recipe']['ItemResult']
                    if not isinstance(recipes_linked, list):
                        recipes_linked = [recipes_linked]
                
                # 👇 這裡就是全新的「起源雷達系統」👇
                if not recipes_linked:
                    source_msgs = []
                    if links:
                        if 'GilShopItem' in links: source_msgs.append("💰 **NPC 商店販售** (準備好你的 Gil)")
                        if 'SpecialShop' in links or 'CustomTalk' in links: source_msgs.append("🔄 **特殊商店兌換** (可能是神典石、神話/戰績點、活動票據或蠻族貨幣)")
                        if 'GCScripShopItem' in links: source_msgs.append("🛡️ **大軍團商店** (軍票兌換)")
                        if 'InstanceContent' in links or 'ContentFinderCondition' in links: source_msgs.append("⚔️ **副本掉落** (快去打本吧！)")
                        if 'Achievement' in links: source_msgs.append("🏆 **成就獎勵**")
                        if 'Quest' in links or 'ItemReward' in links: source_msgs.append("📜 **任務獎勵** (主線或支線)")
                        if 'GatheringItem' in links: source_msgs.append("🪓 **採集取得** (園藝工 / 採礦工)")
                        if 'FishParameter' in links or 'SpearfishingItem' in links: source_msgs.append("🎣 **釣魚 / 刺魚取得**")
                        if 'TreasureHunt' in links: source_msgs.append("🗺️ **藏寶圖掉落**")

                    st.warning(f"⚠️ 【{single_item_input}】不能透過工匠製作喔！")
                    
                    if source_msgs:
                        st.info("**📡 系統雷達偵測到的可能來源：**\n" + "\n".join([f"- {msg}" for msg in source_msgs]))
                    else:
                        st.info("📡 系統查無明確來源 (可能是商城課金道具、絕版品、盲盒開出、或是純怪物掉落)。")
                        
                    # 貼心功能：即使不能做，也幫你查交易板有沒有人賣！
                    with st.spinner("🛒 順便幫你看看交易板有沒有人賣..."):
                        market_price, market_world = get_lowest_price_info(crafted_item_id, selected_dc)
                        if market_price > 0:
                            st.success(f"💡 好消息！這個東西可以直接用買的！\n最低價：**{market_price} G** (位於 {market_world})")
                        else:
                            st.error("📉 目前交易板上無人販售 (或者是綁定不可交易物品)。")

                # 如果可以製作，執行原本的算錢邏輯
                else:
                    recipe_id = recipes_linked[0]
                    recipe_url = f"https://xivapi.com/Recipe/{recipe_id}"
                    recipe_data = requests.get(recipe_url).json()
                    
                    ingredients = []
                    for i in range(10):
                        ing_data = recipe_data.get(f"ItemIngredient{i}")
                        if ing_data is not None:
                            ing_id = ing_data['ID']
                            ing_tw_name = item_id_to_name.get(ing_id, ing_data['Name'])
                            ingredients.append({
                                "id": ing_id,
                                "name": ing_tw_name,
                                "amount": recipe_data.get(f"AmountIngredient{i}")
                            })
                            
                    with st.spinner("🛒 正在跑遍各大伺服器交易板..."):
                        crafted_price, crafted_world = get_lowest_price_info(crafted_item_id, selected_dc)
                        total_cost = 0
                        mat_details = []
                        for ing in ingredients:
                            price, world = get_lowest_price_info(ing['id'], selected_dc)
                            cost = price * ing['amount']
                            total_cost += cost
                            mat_details.append({
                                "材料名稱": ing['name'],
                                "需求數量": ing['amount'],
                                "最低單價": price,
                                "總成本": cost,
                                "🛒 最便宜伺服器": world
                            })
                        profit = crafted_price - total_cost

                    st.markdown("---")
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric(label=f"成品最低售價 ({crafted_world})", value=f"{crafted_price} G")
                    col_b.metric(label="材料總成本", value=f"{total_cost} G")
                    col_c.metric(label="✨ 預期淨利潤", value=f"{profit} G", delta=f"{profit} G")
                    st.markdown("#### 📝 製作材料採購清單")
                    st.dataframe(mat_details, use_container_width=True)

            except Exception as e:
                st.error("❌ 網路連線錯誤，請稍後再試。")

# === 分頁二：市場海選排行榜 (維持原樣) ===
with tab2:
    st.markdown("### 📈 批次掃描海選 (由高至低排序)")
    with st.form("scan_form"):
        batch_dc = st.selectbox("🌐 選擇大區：", ["陸行鳥", "莫古力", "貓區", "豆豆柴"], key="batch_dc")
        default_items = "雨衣\n顯貴短上衣\n古典大劍"
        user_input = st.text_area("📋 輸入進貨清單 (每一行一個)：", value=default_items, height=150)
        submitted = st.form_submit_button("批次分析啟動 🚀", type="primary")

    if submitted:
        target_list = [item.strip() for item in user_input.split('\n') if item.strip()]
        st.info(f"開始掃描 {len(target_list)} 項物品... 請稍候！")
        progress_bar = st.progress(0)
        leaderboard = []
        
        for idx, target_item in enumerate(target_list):
            if target_item not in name_to_item_id:
                progress_bar.progress((idx + 1) / len(target_list))
                continue
                
            crafted_item_id = name_to_item_id[target_item]
            item_url = f"https://xivapi.com/Item/{crafted_item_id}"
            
            try:
                item_res = requests.get(item_url).json()
                links = item_res.get('GameContentLinks')
                recipes_linked = []
                if links and 'Recipe' in links and 'ItemResult' in links['Recipe']:
                    recipes_linked = links['Recipe']['ItemResult']
                    if not isinstance(recipes_linked, list):
                        recipes_linked = [recipes_linked]
                
                if not recipes_linked:
                    progress_bar.progress((idx + 1) / len(target_list))
                    continue
                    
                recipe_id = recipes_linked[0]
                recipe_url = f"https://xivapi.com/Recipe/{recipe_id}"
                recipe_data = requests.get(recipe_url).json()
                
                ingredients = []
                for i in range(10):
                    ing_data = recipe_data.get(f"ItemIngredient{i}")
                    if ing_data is not None:
                        ingredients.append({"id": ing_data['ID'], "amount": recipe_data.get(f"AmountIngredient{i}")})

                crafted_price, _ = get_lowest_price_info(crafted_item_id, batch_dc)
                total_cost = sum(get_lowest_price_info(ing['id'], batch_dc)[0] * ing['amount'] for ing in ingredients)
                profit = crafted_price - total_cost

                leaderboard.append({
                    "物品名稱": target_item,
                    "預期淨利潤 (G)": profit,
                    "市場售價 (G)": crafted_price,
                    "材料成本 (G)": total_cost
                })
                time.sleep(0.5)
            except:
                pass
            progress_bar.progress((idx + 1) / len(target_list))

        if leaderboard:
            leaderboard.sort(key=lambda x: x['預期淨利潤 (G)'], reverse=True)
            for i, item in enumerate(leaderboard):
                item["排名"] = i + 1
            st.success("🎉 掃描完成！")
            st.dataframe(leaderboard, use_container_width=True, hide_index=True)
        else:
            st.warning("沒有找到可以製作的物品。")
