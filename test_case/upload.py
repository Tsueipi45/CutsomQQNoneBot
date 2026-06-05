import time
import logging
import asyncio

from maimai_py import MaimaiClient, PlayerIdentifier, ArcadeProvider, DivingFishProvider

# 配置日志输出
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
_log = logging.getLogger(__name__)

maimai = MaimaiClient()

async def upload_scores(qrcode_content: str, divingfish_update_token: str, developer_token: str):
    _log.info("[upload_scores] 开始执行上传流程")
    start_time = time.perf_counter()

    qrcode_content = qrcode_content.strip()
    if not qrcode_content or not divingfish_update_token:
        _log.error("❌ 凭证缺失，请检查输入的二维码内容或查分器 Token。")
        return

    try:
        # 1. 解析二维码获取街机凭证
        _log.info("正在解析二维码...")
        identifier = await maimai.qrcode(qrcode_content)
        arcade_credentials = identifier.credentials
        _log.info("✅ 二维码解析成功，已自动提取街机凭证。")

        # 2. 初始化查分器 Provider
        divingfish = DivingFishProvider(developer_token=developer_token) if developer_token else DivingFishProvider()

        # 3. 拉取成绩
        _log.info("正在从街机网络拉取成绩...")
        arcade_id = PlayerIdentifier(credentials=arcade_credentials)
        scores = await maimai.scores(arcade_id, provider=ArcadeProvider())

        # 4. 上传到查分器
        _log.info("正在将成绩上传至查分器...")
        diving_id = PlayerIdentifier(credentials=divingfish_update_token)
        await maimai.updates(diving_id, scores.scores, provider=divingfish)

        elapsed = time.perf_counter() - start_time
        _log.info(f"✅ 成绩已成功上传至查分器！共上传 {len(scores.scores)} 条记录。耗时：{elapsed:.2f} 秒")

    except Exception as e:
        elapsed = time.perf_counter() - start_time
        _log.error(f"❌ 执行失败，错误信息：{e}\n耗时：{elapsed:.2f} 秒")

async def main():
    # ==========================================
    # 在这里直接修改你的凭证字段
    # ==========================================
    QRCODE_CONTENT = "改qrcode"
    DIVINGFISH_UPDATE_TOKEN = "改水鱼token"
    
    DIVINGFISH_DEV_TOKEN = " " 

    await upload_scores(
        qrcode_content=QRCODE_CONTENT,
        divingfish_update_token=DIVINGFISH_UPDATE_TOKEN,
        developer_token=DIVINGFISH_DEV_TOKEN
    )

if __name__ == "__main__":
    asyncio.run(main())