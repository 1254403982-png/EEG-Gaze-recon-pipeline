import asyncio
import logging
import os
import time

import cv2
import dotenv

from g3pylib import connect_to_glasses


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


async def stream_rtsp() -> None:
    hostname = os.environ.get("G3_HOSTNAME")

    if not hostname:
        raise RuntimeError(
            "没有找到 G3_HOSTNAME。"
            "请在项目根目录创建 .env 文件，并写入："
            "G3_HOSTNAME=tg03b-你的设备序列号"
        )

    logging.info("正在连接眼动仪：%s", hostname)

    async with connect_to_glasses.with_hostname(
        hostname,
        using_zeroconf=True,
    ) as g3:
        logging.info("已连接 Tobii Pro Glasses 3")

        async with g3.stream_rtsp(
            scene_camera=True,
            gaze=True,
        ) as streams:

            async with streams.gaze.decode() as gaze_stream:
                async with streams.scene_camera.decode() as scene_stream:

                    while True:
                        frame, frame_timestamp = await scene_stream.get()
                        gaze, gaze_timestamp = await gaze_stream.get()

                        # 跳过没有有效时间戳的数据
                        while (
                            frame_timestamp is None
                            or gaze_timestamp is None
                        ):
                            if frame_timestamp is None:
                                frame, frame_timestamp = (
                                    await scene_stream.get()
                                )

                            if gaze_timestamp is None:
                                gaze, gaze_timestamp = (
                                    await gaze_stream.get()
                                )

                        # gaze 时间戳落后于当前视频帧时，
                        # 继续读取 gaze，直到追上视频帧
                        while gaze_timestamp < frame_timestamp:
                            gaze, gaze_timestamp = (
                                await gaze_stream.get()
                            )

                            while gaze_timestamp is None:
                                gaze, gaze_timestamp = (
                                    await gaze_stream.get()
                                )

                        # PyAV 视频帧转成 OpenCV 图像
                        image = frame.to_ndarray(format="bgr24")

                        if gaze is not None and "gaze2d" in gaze:
                            gaze2d = gaze["gaze2d"]

                            x_norm = float(gaze2d[0])
                            y_norm = float(gaze2d[1])

                            height, width = image.shape[:2]

                            pixel_x = int(x_norm * width)
                            pixel_y = int(y_norm * height)

                            # 仅在画面范围内绘制
                            if (
                                0 <= pixel_x < width
                                and 0 <= pixel_y < height
                            ):
                                # 红色外圈
                                cv2.circle(
                                    image,
                                    (pixel_x, pixel_y),
                                    15,
                                    (0, 0, 255),
                                    3,
                                )

                                # 中心红点
                                cv2.circle(
                                    image,
                                    (pixel_x, pixel_y),
                                    3,
                                    (0, 0, 255),
                                    -1,
                                )

                                text = (
                                    f"Gaze "
                                    f"({x_norm:.3f}, {y_norm:.3f})"
                                )

                                cv2.putText(
                                    image,
                                    text,
                                    (20, 40),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.8,
                                    (0, 0, 255),
                                    2,
                                )

                                logging.info(
                                    "frame_ts=%.6f gaze_ts=%.6f "
                                    "gaze2d=(%.4f, %.4f) "
                                    "pixel=(%d, %d)",
                                    frame_timestamp,
                                    gaze_timestamp,
                                    x_norm,
                                    y_norm,
                                    pixel_x,
                                    pixel_y,
                                )

                        cv2.imshow(
                            "Tobii Pro Glasses 3 Live Gaze",
                            image,
                        )

                        key = cv2.waitKey(1) & 0xFF

                        # q：退出
                        if key == ord("q"):
                            break

                        # s：保存当前带红圈画面
                        if key == ord("s"):
                            filename = (
                                f"tobii_gaze_{time.time():.3f}.png"
                            )

                            cv2.imwrite(filename, image)
                            logging.info("已保存：%s", filename)


def main() -> None:
    dotenv.load_dotenv()

    try:
        asyncio.run(stream_rtsp())
    except KeyboardInterrupt:
        logging.info("程序已停止")
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()