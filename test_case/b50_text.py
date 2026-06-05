import logging
import asyncio

from maimai_py import MaimaiClient, PlayerIdentifier, DivingFishProvider

# 配置日志输出
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
_log = logging.getLogger(__name__)

maimai = MaimaiClient()

async def get_b50(username: str, developer_token: str):
    _log.info(f"开始获取玩家 {username} 的 B50 数据...")
    
    if not developer_token or not username:
        _log.error("❌ 缺少查分器 Developer Token 或查询用户名。")
        return

    try:
        # 初始化查分器 Provider
        divingfish = DivingFishProvider(developer_token=developer_token)
        
        # 获取指定玩家的所有成绩
        my_scores = await maimai.scores(PlayerIdentifier(username=username), provider=divingfish)
        
        _log.info("✅ 数据获取成功！\n")
        
        print("=" * 60)
        print(f" 玩家: {username} | 总 Rating: {my_scores.rating}")
        print("=" * 60)

        # maimai-py 的 ScoreList 通常会解析并包含 b35 和 b15 属性
        b35_list = getattr(my_scores, 'b35', [])
        b15_list = getattr(my_scores, 'b15', [])
        
        # 如果库直接支持 b35 和 b15
        if b35_list or b15_list:
            print("--- B35 (旧版本) ---")
            for i, s in enumerate(b35_list, 1):
                # 安全获取属性，避免 AttributeError
                song_name = getattr(s, 'title', getattr(s, 'song_name', 'Unknown Title'))
                level = s.level_index.name if hasattr(s, 'level_index') else "UNKNOWN"
                rating = getattr(s, 'ra', getattr(s, 'rating', 0))
                print(f" {i:2d}. {song_name} [{level}] - {s.achievements}% -> Rating: {rating}")

            print("\n--- B15 (新版本) ---")
            for i, s in enumerate(b15_list, 1):
                song_name = getattr(s, 'title', getattr(s, 'song_name', 'Unknown Title'))
                level = s.level_index.name if hasattr(s, 'level_index') else "UNKNOWN"
                rating = getattr(s, 'ra', getattr(s, 'rating', 0))
                print(f" {i:2d}. {song_name} [{level}] - {s.achievements}% -> Rating: {rating}")
        
        # 作为兼容备用方案：如果未解析拆分版本，手动按单曲 rating(ra) 降序排列展示前 50
        else:
            print("--- Top 50 成绩 (混合版本) ---")
            sorted_scores = sorted(my_scores.scores, key=lambda x: getattr(x, 'ra', getattr(x, 'rating', 0)) or 0, reverse=True)
            for i, s in enumerate(sorted_scores[:50], 1):
                song_name = getattr(s, 'title', getattr(s, 'song_name', 'Unknown Title'))
                level = s.level_index.name if hasattr(s, 'level_index') else "UNKNOWN"
                rating = getattr(s, 'ra', getattr(s, 'rating', 0))
                print(f" {i:2d}. {song_name} [{level}] - {s.achievements}% -> Rating: {rating}")

        print("=" * 60)

    except Exception as e:
        _log.error(f"❌ 获取 B50 失败，错误信息：{e}")

async def main():
    # ==========================================
    # 在这里直接修改你的凭证与查询字段
    # ==========================================
    USERNAME = "username"  
    DIVINGFISH_DEV_TOKEN = ""  

    await get_b50(
        username=USERNAME,
        developer_token=DIVINGFISH_DEV_TOKEN
    )

if __name__ == "__main__":
    asyncio.run(main())