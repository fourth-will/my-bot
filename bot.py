import logging
import os
import re
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
from telegram.error import TimedOut, NetworkError

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ========== خادم وهمي لإشباع فحص المنفذ في Render ==========
class FakeHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running')

def start_fake_server():
    port = int(os.environ.get('PORT', 5000))
    server = HTTPServer(('0.0.0.0', port), FakeHandler)
    logging.info(f'Fake server running on port {port}')
    server.serve_forever()

# =========================================================
#  قاعدة معرفات الملفات الموحّدة (الكورس الأول والثاني)
# =========================================================
LECTURE_FILE_IDS = {
    # ========== الكورس الأول ==========
    "first_stage_first_course_Analytical Chemistry_نظري_1": "BQACAgIAAxkBAAEpAAEEaftRJ14ZLgTv3e5sqxsrtTI1DqUAAqCkAAKGsdhLaAoVlsKOg3Y7BA",
    "first_stage_first_course_Analytical Chemistry_نظري_2": [
        "BQACAgIAAxkBAAEpAAEOaftSLlID-sActyqy5wodwDTn1p0AAqKkAAKGsdhLImORYRRYf007BA",
        "BQACAgIAAxkBAAEpAAEMaftSLsMlPWmSwBbTkQodCoRduAUAAqGkAAKGsdhLbGND1PceLLg7BA",
        "BQACAgIAAxkBAAEpAAENaftSLmelRUbzKiuPZsDmD_LUlVkAAqOkAAKGsdhLgdLVe7vWlTU7BA"
    ],
    "first_stage_first_course_Analytical Chemistry_عملي_1": "BQACAgIAAxkBAAEpAAEZaftS2W3ux_JTMA7fJwaFbI2-JEIAAqSkAAKGsdhLFlKt7LudY-Y7BA",
    "first_stage_first_course_Analytical Chemistry_عملي_2": [
        "BQACAgIAAxkBAAEpAAEbaftTNf90dTRbHBkV1a-myAAB7NmKAAKlpAAChrHYS6GGBzKFlmB1OwQ",
        "BQACAgIAAxkBAAEpAAEcaftTNQ2hdDFiZPlsLXFNsy063MMAAqekAAKGsdhLk_OrBKZOtGg7BA",
        "BQACAgIAAxkBAAEpAAEfaftTNVcuuiuUgKYVcAiIE2YKZ-QAAqmkAAKGsdhLRLeO3_rVT5A7BA",
        "BQACAgIAAxkBAAEpAAEeaftTNabiGSQP5N887zKYt0DjIEUAAqikAAKGsdhLGl10ZU31H4g7BA",
        "BQACAgIAAxkBAAEpAAEdaftTNTZ1sOQWaExQfyZOyfpNsLMAAqakAAKGsdhLiVzmCgeCrUw7BA"
    ],
    "first_stage_first_course_Analytical Chemistry_عملي_3": "BQACAgIAAxkBAAEpAAEnaftT7RNeA2suOjYCoHt2XAET1vsAAqqkAAKGsdhLDjhSlnNU6Xg7BA",
    "first_stage_first_course_Medical Physics_نظري_1": "BQACAgIAAxkBAAEpAAEwaftUMw1ZhaZW-Uk6nQmuRHAS6M8AAq6kAAKGsdhLMautoHD4K2g7BA",
    "first_stage_first_course_Medical Physics_نظري_2": "BQACAgIAAxkBAAEpAAEyaftUZ9Tctykmt4ZdtSv6pEJsDqEAAq-kAAKGsdhLvkC5EaK14u07BA",
    "first_stage_first_course_Medical Physics_نظري_3": [
        "BQACAgIAAxkBAAEpAAE0aftUkC9kPs-Oe18Uucz8LUbTe8wAArCkAAKGsdhLymxAnY9xW9g7BA",
        "BQACAgIAAxkBAAEpAAE1aftUkKLJWiIdRWeGl23odz4vZI0AArGkAAKGsdhLGV4AAcmKPsknOwQ"
    ],
    "first_stage_first_course_Medical Physics_نظري_4": "BQACAgIAAxkBAAEpAAE5aftU3toeJvIYKq7I7nWRjvJed0MAArKkAAKGsdhLK8hLe5I_XLI7BA",
    "first_stage_first_course_Medical Physics_نظري_5": "BQACAgIAAxkBAAEpAAE7aftVA8Ny_k3HScwRHgJVkZOVhsUAArOkAAKGsdhLRafaDffkTbE7BA",
    "first_stage_first_course_Medical Physics_نظري_6": "BQACAgIAAxkBAAEpAAE9aftVJfnS8zIhM4OUZ_b44VLJDsoAArSkAAKGsdhLJEwZti_uTOE7BA",
    "first_stage_first_course_Medical Physics_عملي_1": "BQACAgIAAxkBAAEpAAE_aftVRlQM2guplihKz-k90bswUeoAArWkAAKGsdhL57GHJY9OvU47BA",
    "first_stage_first_course_Medical Physics_عملي_2": "BQACAgIAAxkBAAEpAAFBaftVYWVFG0bMUZUtGs32kLhmcaEAArakAAKGsdhL5HZAz7frkyM7BA",
    "first_stage_first_course_Medical Physics_عملي_3": "BQACAgIAAxkBAAEpAAFDaftVhJQsNviJBZUMlzJKqzILkroAArikAAKGsdhLmAlR23SzWpA7BA",
    "first_stage_first_course_حقوق الإنسان_نظري_1": [
        "BQACAgIAAxkBAAEpAAFFaftVqlzfFGxTWOly5H3InZCZnkYAArukAAKGsdhLxt0ii-p4Q_o7BA",
        "BQACAgIAAxkBAAEpAAFGaftVqh_ZOJ4LFckF1Ja08zFKOZwAArykAAKGsdhLCkI2IsKPcuI7BA"
    ],
    "first_stage_first_course_Biostatistics_نظري_1": "BQACAgIAAxkBAAEpAAFNaftWR8G-D_WEzfDlAAGThUCb0S6yAAK9pAAChrHYS1TyOe7vFxFMOwQ",
    "first_stage_first_course_Biostatistics_نظري_2": [
        "BQACAgIAAxkBAAEpAAFPaftWaK1utgKd8ddRk3Cu1TFFkSYAAr6kAAKGsdhL27LDj2KV6987BA",
        "BQACAgIAAxkBAAEpAAFQaftWaDoEvt4m9RLI0yThxwwXqWgAAr-kAAKGsdhLz9D3GYT3arY7BA"
    ],
    "first_stage_first_course_Biostatistics_نظري_3": "BQACAgIAAxkBAAEpAAFTaftWrhpDRIxoaV1KQvU2Frpash0AAsGkAAKGsdhLLpfAEhKrbPI7BA",
    "first_stage_first_course_Biostatistics_نظري_4": "BQACAgIAAxkBAAEpAAFVaftW0hBtpz4M5TcC3CgdeiwxvbMAAsKkAAKGsdhLeEog8ef6OLo7BA",
    "first_stage_first_course_Terminology_نظري_1": "BQACAgIAAxkBAAEpAAFaaftW-RWDHSz2bNZ144PrCWC2FMkAAsOkAAKGsdhL6fN6BLM_GUw7BA",
    "first_stage_first_course_Terminology_نظري_2": "BQACAgIAAxkBAAEpAAFdaftXHmKDidfUR4GnLdFQ824BYEwAAsSkAAKGsdhLKec1SqjGuwY7BA",
    "first_stage_first_course_Terminology_نظري_3": "BQACAgIAAxkBAAEpAAFfaftXOYjsGKaSTe5i7Vv5VhCi1OEAAsWkAAKGsdhL6PIMPGBiEr07BA",
    "first_stage_first_course_Terminology_نظري_4": "BQACAgIAAxkBAAEpAAFhaftXUhrvq4_rKFfjP07qnRMVLm8AAsakAAKGsdhLcL2qrQgtLqw7BA",
    "first_stage_first_course_Terminology_نظري_5": "BQACAgIAAxkBAAEpAAFjaftXbOsHS1uKqeF_HXIDPQQVemEAAsekAAKGsdhLpPqKdtbRcPA7BA",
    "first_stage_first_course_Terminology_نظري_6": "BQACAgIAAxkBAAEpAAFlaftXiFiveM9kR8IXh4JAeC7gHfIAAsikAAKGsdhLKVBKFAmc9fY7BA",
    "first_stage_first_course_Terminology_نظري_7": "BQACAgIAAxkBAAEpAAFnaftXoi7lIU3F-vOOVJazvW2b6UEAAsqkAAKGsdhLXOtaah3eNLw7BA",
    "first_stage_first_course_Terminology_نظري_8": "BQACAgIAAxkBAAEpAAFpaftXyVqCe_AwoFT_Pk14rvZee-kAAsykAAKGsdhLqsNU4nlxtXE7BA",
    "first_stage_first_course_Histology_نظري_1": [
        "BQACAgIAAxkBAAEpAAFsaftX8_TAz7-LDXo2QroWRtoMf7AAAs-kAAKGsdhLUCSVGvtnOHM7BA",
        "BQACAgIAAxkBAAEpAAFraftX81Ub5Bbt2hSe0nNHoTRz9YEAAtCkAAKGsdhL8XUFqAABNfFFOwQ"
    ],
    "first_stage_first_course_Histology_نظري_2": [
        "BQACAgIAAxkBAAEpAAFwaftYJU_yzBa2XJeKqQ8EMqQj2JMAAtGkAAKGsdhLnK2gKeSllxg7BA",
        "BQACAgIAAxkBAAEpAAFvaftYJUJr6dY2KwtsCl2xTynCkoUAAtKkAAKGsdhLg79dVvAkmBA7BA"
    ],
    "first_stage_first_course_Histology_نظري_3": [
        "BQACAgIAAxkBAAEpAAF0aftYUiBnOhPlgPjUqNE-S8_eQqMAAtOkAAKGsdhLgSe6cubUQ9Y7BA",
        "BQACAgIAAxkBAAEpAAF1aftYUqP9jGlm_ZxY2BHxcQ9ftTsAAtSkAAKGsdhLQciQUYuR-Z47BA",
        "BQACAgIAAxkBAAEpAAFzaftYUkl12Lc_O-kfJDQO2DW61j4AAtWkAAKGsdhLzrzsm5GXPbQ7BA"
    ],
    "first_stage_first_course_Histology_نظري_4": "BQACAgIAAxkBAAEpAAF5aftYk4wYokT9H8STT4a_EG-BLRwAAtmkAAKGsdhL3cda98HewVA7BA",
    "first_stage_first_course_Histology_نظري_5": [
        "BQACAgIAAxkBAAEpAAF7aftYsIgRAm2OHV_wvr8zjmC1CGUAAtukAAKGsdhLiwPZCC_d9Ec7BA",
        "BQACAgIAAxkBAAEpAAF8aftYsJT-hf66WWw9K0S3iKAyf-MAAtqkAAKGsdhLq6e4aU4diUk7BA"
    ],
    "first_stage_first_course_Histology_نظري_6": [
        "BQACAgIAAxkBAAEpAAGBaftY2wABR6_KA4VmOxSGPYy1Y6Z1AALdpAAChrHYS6qrpDMLsgYHOwQ",
        "BQACAgIAAxkBAAEpAAGAaftY2xDTvIWlltkP4_cD2xyqjcUAAtykAAKGsdhLXEjSTeJh97Q7BA",
        "BQACAgIAAxkBAAEpAAF_aftY286Ha1vJOvbSTiUbxIKLg_YAAt6kAAKGsdhL2M-aQ0OOLJM7BA"
    ],
    "first_stage_first_course_Histology_عملي_1": "BQACAgIAAxkBAAEpAAGHaftZwquYASGsb52Z9hqMKLbEzrcAAgilAAKGsdhLwVB7omBxugg7BA",
    "first_stage_first_course_Histology_عملي_2": "BQACAgIAAxkBAAEpAAGJaftZ5Poxz9YIScMlVPQ61NkktMAAAgmlAAKGsdhL8AKPRIryShg7BA",
    "first_stage_first_course_Anatomy_نظري_1": "BQACAgIAAxkBAAEpAAGLaftaDvA4i9khtmsxE8wMj4hbGqkAAg-lAAKGsdhLQ26IqMI47PQ7BA",
    "first_stage_first_course_Anatomy_نظري_2": "BQACAgIAAxkBAAEpAAGNaftaWXNGhdEOC4khxoGwVfFZcSIAAhClAAKGsdhL3p_qrW7oOxs7BA",
    "first_stage_first_course_Anatomy_نظري_3": "BQACAgIAAxkBAAEpAAGPaftadsF-nUNVzmhjoOh5DdDTgdYAAhGlAAKGsdhL2QouH0eQRN07BA",
    "first_stage_first_course_Anatomy_نظري_4": "BQACAgIAAxkBAAEpAAGRaftaligTiWcvCiSgcy1LRZ5VnEAAAhKlAAKGsdhLrsayVVWO3rc7BA",
    "first_stage_first_course_Anatomy_نظري_5": "BQACAgIAAxkBAAEpAAGTaftaw8K_pLzdJxXCd6cwKBaBZ6UAAhOlAAKGsdhL6AqEaYd-jq47BA",
    "first_stage_first_course_Anatomy_نظري_6": "BQACAgIAAxkBAAEpAAGVaftbBhBE0Om-4X_TlFTC6_9oWJsAAhSlAAKGsdhLf1_RIb2cui47BA",
    "first_stage_first_course_Anatomy_نظري_7": "BQACAgIAAxkBAAEpAAGXaftbNPdcfXu374x4F9UcKS9X1LoAAhWlAAKGsdhLsvrqOMEAAXwyOwQ",
    "first_stage_first_course_Anatomy_نظري_8": "BQACAgIAAxkBAAEpAAGZaftbU9EubuKdfCVHMf8wtOfgq1UAAhalAAKGsdhLyyVYOm6D-pY7BA",
    "first_stage_first_course_Anatomy_عملي_1": "BQACAgIAAxkBAAEpAAGbaftbdcf0EFe_5NIYeEDuz3xbHVcAAhelAAKGsdhLX_KsaajlpRs7BA",
    "first_stage_first_course_Anatomy_عملي_2": "BQACAgIAAxkBAAEpAAGdaftbj-1U6HpI1dPn6-g-iyp6TwMAAhmlAAKGsdhLTzIv4K0t88k7BA",

    # ========== الكورس الثاني ==========
    "first_stage_second_course_Pharmaceutical Calculations_نظري_1": "BQACAgIAAxkBAAEpAAGlafte_HW_cc00H6VkQ-CqXGXQ5dkAAhqlAAKGsdhLo-2bNuiveYc7BA",
    "first_stage_second_course_Pharmaceutical Calculations_نظري_2": "BQACAgIAAxkBAAEpAAGnaftfMOISch6kj-RMzUk7mzuKSc8AAhulAAKGsdhLG7WqAtCQ_NM7BA",
    "first_stage_second_course_Pharmaceutical Calculations_نظري_3": [
        "BQACAgIAAxkBAAEpAAGpaftfS1B9xAa0n8VKVu4xvzrrqI8AAhylAAKGsdhLb5K5HiO2_-c7BA",
        "BQACAgIAAxkBAAEpAAGqaftfS9jeJQFxiDYE8vFb_Z9elQ4AAh2lAAKGsdhLGGU6JPjHuKU7BA"
    ],
    "first_stage_second_course_Pharmaceutical Calculations_نظري_4": "BQACAgIAAxkBAAEpAAGtaftfeC5zMiuXIWMYmwI1Ft6xnOcAAh6lAAKGsdhL6yYRVwQLv847BA",
    "first_stage_second_course_Pharmaceutical Calculations_نظري_5": "BQACAgIAAxgBAAEpAAGvaftflH3u9xNyTCscn2vYkpp3zMYAAh-lAAKGsdhL38Y0mW4XEiM7BA",
    "first_stage_second_course_Pharmaceutical Calculations_نظري_6": [
        "BQACAgIAAxkBAAEpAAGxaftfuEsqZ2wuQI25zqrkvE0hQnYAAiClAAKGsdhLrqUypGJ7j087BA",
        "BQACAgIAAxkBAAEpAAGyaftfuPWMdruIOXQnw6gSF2CKdZcAAiGlAAKGsdhLWoAz_Qtt66I7BA"
    ],
    "first_stage_second_course_Pharmaceutical Calculations_نظري_7": "BQACAgIAAxkBAAEpAAG3aftf5wimU81QI6YfvUBZ1hapQ00AAiOlAAKGsdhLx5UtgyVaiz47BA",
    "first_stage_second_course_Pharmaceutical Calculations_نظري_8": "BQACAgIAAxkBAAEpAAG5aftf_1V2b4GgIl_F42M2Mgb0xiQAAiSlAAKGsdhLoGn6wdxKzAU7BA",
    "first_stage_second_course_Pharmaceutical Calculations_نظري_9": "BQACAgIAAxkBAAEpAAG9aftgGprzRZVVOVTMsom2xc7MUJsAAiWlAAKGsdhLr5sT3XHFFr87BA",
    "first_stage_second_course_Pharmaceutical Calculations_عملي_1": "BQACAgIAAxkBAAEpAAG_aftgNi0b-unuF5WET2bsVFJ31Z8AAielAAKGsdhL_9ZQb0RH9kg7BA",
    "first_stage_second_course_Pharmaceutical Calculations_عملي_2": [
        "BQACAgIAAxkBAAEpAAHBaftgcn1w0UccB6F9CgtAQSrr_ToAAimlAAKGsdhLz8RNUmjyVkI7BA",
        "BQACAgIAAxkBAAEpAAHCaftgcrdEWfXBPKzh0QmUpmQp6rgAAiilAAKGsdhLKR0_DBXNc-E7BA"
    ],
    "first_stage_second_course_Pharmaceutical Calculations_عملي_3": "BQACAgIAAxkBAAEpAAHHaftgoV_WcMwaqIKozP3Vse7ix9kAAiqlAAKGsdhLdZcjQSITHxw7BA",
    "first_stage_second_course_Pharmaceutical Calculations_عملي_4": "BQACAgIAAxkBAAEpAAHJaftguFOejespzqchNiAs3fkKqjUAAiylAAKGsdhL47BPk8A3Xm87BA",
    "first_stage_second_course_Pharmaceutical Calculations_عملي_5": "BQACAgIAAxkBAAEpAAHLaftg1QW_hFLPmAiVP4l5GmGuRA4AAi2lAAKGsdhL6EiwGgu5Fcc7BA",
    "first_stage_second_course_Pharmaceutical Calculations_عملي_6": "BQACAgIAAxkBAAEpAAHNaftg76Fx3nbQrSlRIp5pYaE7enMAAi6lAAKGsdhLvkBmIBXtTjI7BA",
    "first_stage_second_course_Pharmaceutical Calculations_عملي_7": "BQACAgIAAxkBAAEpAAHPafthCC_8soNXASyrXqeA6beGGD0AAi-lAAKGsdhLxw6rq0gAAY_HOwQ",
    "first_stage_second_course_Pharmaceutical Calculations_مصادر": "BQACAgIAAxkBAAEpATFp-2YEiGvvfpxwwJMTsiT9kWiJZAACAqIAAoax2EscQpcg141-YzsE",
    "first_stage_second_course_Organic Chemistry I_نظري_1": "BQACAgIAAxkBAAEpAAHRafthMDu98fzuhivs8WlcI5YwIxMAAjClAAKGsdhLWq_xyeOfj507BA",
    "first_stage_second_course_Organic Chemistry I_نظري_2": "BQACAgIAAxkBAAEpAAHTafthXJR8P-OWe_NL9PzTAAFh4olBAAIxpQAChrHYSyIYDiWg-xMYOwQ",
    "first_stage_second_course_Organic Chemistry I_نظري_3": "BQACAgIAAxkBAAEpAAHZafthe43WudD7XjgiPy_w_NMe2xwAAjKlAAKGsdhL0SVX6dFwGQM7BA",
    "first_stage_second_course_Organic Chemistry I_نظري_4": "BQACAgIAAxkBAAEpAAHbafthl-iKQgjy1EAobhVan3Er7s0AAjOlAAKGsdhLJdfQ9P8iLto7BA",
    "first_stage_second_course_Organic Chemistry I_نظري_5": "BQACAgIAAxkBAAEpAAHdafth83YcbClawSpn3T7y0I6rNtsAAjSlAAKGsdhLdiwSs1_xJ287BA",
    "first_stage_second_course_Organic Chemistry I_نظري_6": "BQACAgIAAxkBAAEpAAHfaftiCwiEkyZMHCTsFlsox7bYeDMAAjWlAAKGsdhLxo_VOm-p1FI7BA",
    "first_stage_second_course_Organic Chemistry I_نظري_7": "BQACAgIAAxkBAAEpAAHhaftiI5hLWZ4xGCQ-W_SYd7O4IP0AAjalAAKGsdhLB-xjovsvPgU7BA",
    "first_stage_second_course_Organic Chemistry I_نظري_8": "BQACAgIAAxkBAAEpAAHjaftiOrswNUD2dUaUGjZrnoqFNZUAAjelAAKGsdhLgj8527oNBOI7BA",
    "first_stage_second_course_Organic Chemistry I_نظري_9": [
        "BQACAgIAAxkBAAEpAAHmaftiU1kn2hy9OgABlpF6YHpsQQy-AAI4pQAChrHYS5mYHoFgXJLIOwQ",
        "BQACAgIAAxkBAAEpAAHlaftiU23meR86OS5MSsEoqE6DjDoAAjmlAAKGsdhLJ4cswS6El6k7BA"
    ],
    "first_stage_second_course_Organic Chemistry I_نظري_10": "BQACAgIAAxkBAAEpAAHpaftieZza1eIpB3YdTXsfiK9C9QkAAjqlAAKGsdhLw-wznAhMxwM7BA",
    "first_stage_second_course_Organic Chemistry I_نظري_11": "BQACAgIAAxkBAAEpAAHraftikfQMyguIdzvb6-MQKvkSusgAAjulAAKGsdhL6WD26Y9vM5E7BA",
    "first_stage_second_course_Organic Chemistry I_نظري_12": "BQACAgIAAxkBAAEpAAHtaftirh6jFpCrdpVHdAT01k3p7MkAAj2lAAKGsdhLuesTS6bws747BA",
    "first_stage_second_course_Organic Chemistry I_نظري_13": "BQACAgIAAxkBAAEpAAHvaftizSe4WE0r52LPKRCHD8fyDfIAAj6lAAKGsdhLSIbUx34ezdw7BA",
    "first_stage_second_course_Organic Chemistry I_نظري_14": "BQACAgIAAxkBAAEpAAHxafti5eA1LZaZW8O1bmQy8Rok5VIAAj-lAAKGsdhLkEDLKxEcSUg7BA",
    "first_stage_second_course_Organic Chemistry I_عملي_1": "BQACAgIAAxkBAAEpAAHzaftjBgiuKvSuMtT7DSmiOZ5j3VwAAmKlAAKGsdhLVCnDKz2UPXY7BA",
    "first_stage_second_course_Organic Chemistry I_عملي_2": [
        "BQACAgIAAxkBAAEpAAH2aftjJVOHZv5IP1IgjHeo0o0uW4EAAmOlAAKGsdhLRdKa9bnxvzE7BA",
        "BQACAgIAAxkBAAEpAAH1aftjJZf6JZFI9hpFiPN0r2mVPDsAAmSlAAKGsdhLOtJGZNWjsFU7BA",
        "BQACAgIAAxkBAAEpAAH3aftjJQcIO0mkkjglA5ptdCz6tTMAAmWlAAKGsdhLbUJIyHSbalA7BA"
    ],
    "first_stage_second_course_Organic Chemistry I_عملي_3": [
        "BQACAgIAAxkBAAEpAAH7aftjY9mhBekqwXLOfnLS5E0MTacAAmalAAKGsdhLYY5hpzJ53bM7BA",
        "BQACAgIAAxkBAAEpAAH8aftjY-zQuPcpEf09Pc2-DvFMXWUAAmelAAKGsdhL4Az1wTsTf2E7BA"
    ],
    "first_stage_second_course_Organic Chemistry I_عملي_4": [
        "BQACAgIAAxkBAAEpAAH_aftjh_Sj6VlGuInLoa9KzpUHL4kAAmilAAKGsdhLxgcFfsB4iD87BA",
        "BQACAgIAAxkBAAEpAQFp-2OHKeLqvQUPfrqBCIG0JnkXrQACaqUAAoax2Es3JW_ED5wCrzsE",
        "BQACAgIAAxkBAAEpAQABaftjh6Eflr31DlfBhVmiZzFINtAAAmmlAAKGsdhL3BH2_dosLWE7BA"
    ],
    "first_stage_second_course_Organic Chemistry I_عملي_5": [
        "BQACAgIAAxkBAAEpAQVp-2PGhd32rlpJ6tlxs_uAylCltwACbKUAAoax2EslbEVEuK4d-jsE",
        "BQACAgIAAxkBAAEpAQZp-2PG9BP9JuXOkRExpIglnfzXVQACa6UAAoax2EvMMChA86TvZzsE"
    ],
    "first_stage_second_course_Computer Sciences_نظري_1": "BQACAgIAAxkBAAEpAQlp-2P5CZvV0ZkAAZsRjyS8TktmoH4AAm2lAAKGsdhLQ15DDdC2K6s7BA",
    "first_stage_second_course_Computer Sciences_نظري_2": [
        "BQACAgIAAxkBAAEpAQ1p-2QxGFmkOW6YU1_qRLzLOyWROQACb6UAAoax2Etn5hHLPK_VCjsE",
        "BQACAgIAAxkBAAEpAQxp-2Qx1G7p8UxUc7-H5rw3-MIi-AACbqUAAoax2Ev5xLOMfMTA2jsE",
        "BQACAgIAAQtp-2QxExcR1hnnFN4bVnNmPE9s5QACcKUAAoax2EseCaNRxlzzPjsE"
    ],
    "first_stage_second_course_Physiology_نظري_1": "BQACAgIAAxkBAAEpARFp-2SFWqDMS-QqTVqDrOM-iNB5LwACcaUAAoax2EsRf56BCMMH0DsE",
    "first_stage_second_course_Physiology_نظري_2": "BQACAgIAAxkBAAEpARNp-2SnUdC9qutO7zqNYNHElE4obAACcqUAAoax2EsyBJWB-kz1iTsE",
    "first_stage_second_course_Physiology_نظري_3": [
        "BQACAgIAAxkBAAEpARVp-2TA62g311tLSK4FuPeoh6dH-QACc6UAAoax2EtIMM6MocP1IzsE",
        "BQACAgIAAxkBAAEpARZp-2TAZL9V1KtfBmGgMF8qr5-0LgACdKUAAoax2EtgxgABdZovlSk7BA"
    ],
    "first_stage_second_course_Physiology_نظري_4": "BQACAgIAAxkBAAEpARlp-2TqWxBMJa6INQ5yIQAB5Olrsb0AAnalAAKGsdhLFE_shnVf6cY7BA",
    "first_stage_second_course_Physiology_نظري_5": "BQACAgIAAxkBAAEpARtp-2UB4FZbkTbI2RHvBy98Y0RDmAACd6UAAoax2EsXISw6-cHx1zsE",
    "first_stage_second_course_Physiology_نظري_6": "BQACAgIAAxkBAAEpAR1p-2UZIXgisTm4WztI6aqmmTjL0wACeKUAAoax2Es8bZZoGqQQWzsE",
    "first_stage_second_course_Physiology_نظري_7": "BQACAgIAAxkBAAEpAR9p-2Uz0drm8n3KUowrXVpIsPVTngACeaUAAoax2EvX4REqfq9_2TsE",
    "first_stage_second_course_Physiology_عملي_1": "BQACAgIAAxkBAAEpASFp-2VLkaoal4K7WneLwciVF6olPQACeqUAAoax2EvVl1LJBUf0CTsE",
    "first_stage_second_course_Physiology_عملي_2": "BQACAgIAAxkBAAEpASNp-2Vl6w8Hl5JFgmWfJMXg84pUDwACe6UAAoax2EuhHHvUiIfa0jsE",
    "first_stage_second_course_Physiology_عملي_3": "BQACAgIAAxkBAAEpASVp-2WBk5eMOB25Fpc3syCzWhHO_QACfKUAAoax2EvZ993_f_w-nTsE",
    "first_stage_second_course_Physiology_عملي_4": "BQACAgIAAxkBAAEpAStp-2We44tnqmzyj_rl-a7gFUFhpQACfaUAAoax2EuUMyi8YqZgqzsE",
    "first_stage_second_course_Physiology_عملي_5": "BQACAgIAAxkBAAEpAS1p-2XCQlxgvD2e_tryOR4Lc4pcKAACfqUAAoax2EvYnDk9VHgqKzsE"
}

# مواد لا يوجد بها قسم عملي
MATERIALS_NO_PRACTICAL = [
    "⚖️ حقوق الإنسان ⚖️",
    "📈 Biostatistics 📈",
    "📝 Terminology 📝",
    "💻 Computer Sciences 💻",
    "🗣️ Arabic Language 🗣️",
]

def clean_material_name(raw_name: str) -> str:
    """إزالة الرموز والإيموجي من اسم المادة ليطابق المفاتيح في القاموس."""
    return re.sub(r'[^a-zA-Z0-9\s\u0621-\u064A]', '', raw_name).strip()

def build_course_keyboard(course_location: str) -> list:
    if course_location == 'first_course':
        return [
            ["🧪 Analytical Chemistry 🧪"],
            ["📊 Medical Physics 📊"],
            ["⚖️ حقوق الإنسان ⚖️"],
            ["📈 Biostatistics 📈"],
            ["📝 Terminology 📝"],
            ["🔬 Histology 🔬"],
            ["🦴 Anatomy 🦴"],
            ["⬅️ رجوع"]
        ]
    else:
        return [
            ["🧮 Pharmaceutical Calculations 🧮"],
            ["⚛️ Organic Chemistry I ⚛️"],
            ["💻 Computer Sciences 💻"],
            ["🗣️ Arabic Language 🗣️"],
            ["🧠 Physiology 🧠"],
            ["⬅️ رجوع"]
        ]

def get_available_lecture_numbers(material_key_base: str) -> list:
    numbers = []
    prefix = material_key_base + "_"
    for key in LECTURE_FILE_IDS:
        if key.startswith(prefix):
            try:
                num = int(key.split("_")[-1])
                numbers.append(num)
            except ValueError:
                continue
    return sorted(set(numbers))

def build_lecture_keyboard(numbers: list) -> list:
    keyboard = []
    for i in range(0, len(numbers), 3):
        row = [str(n) for n in numbers[i:i+3]]
        keyboard.append(row)
    keyboard.append(["⬅️ رجوع"])
    keyboard.append(["🔝 القائمة الرئيسية"])
    return keyboard

async def send_files_by_ids(update: Update, context: ContextTypes.DEFAULT_TYPE, file_ids, caption: str = ""):
    """إرسال الملفات باستخدام معرفاتها من تيليجرام، مع وصف."""
    if isinstance(file_ids, str):
        file_ids = [file_ids]
    for fid in file_ids:
        try:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=fid,
                caption=caption if caption else None
            )
        except Exception as e:
            logging.error(f"خطأ في إرسال الملف {fid}: {e}", exc_info=True)
            await update.message.reply_text("⚠️ فشل إرسال أحد الملفات. تأكد من صلاحية المعرف.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = 'main_menu'
    context.user_data.pop('skip_section_menu', None)
    reply_keyboard = [
        ["🔴 المرحلة الأولى 🔴"],
        ["🔵 المرحلة الثانية 🔵"],
        ["🟠 المرحلة الثالثة 🟠"],
        ["🟣 المرحلة الرابعة 🟣"],
        ["🟢 المرحلة الخامسة 🟢"],
    ]
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text("🔝 القائمة الرئيسية", reply_markup=reply_markup)

async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "الأولى" in text:
        context.user_data['current_stage'] = 'first_stage'
        context.user_data['state'] = 'course_menu'
        reply_keyboard = [
            ["🟧 First course 🟧"],
            ["⬛ Second course ⬛"],
            ["⬅️ رجوع إلى المراحل"]
        ]
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text("قريباً، جاري إضافة باقي المراحل.")
        await start(update, context)

async def handle_course_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "First course" in text:
        context.user_data['current_location'] = 'first_course'
        context.user_data['state'] = 'material_menu'
        reply_keyboard = build_course_keyboard('first_course')
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif "Second course" in text:
        context.user_data['current_location'] = 'second_course'
        context.user_data['state'] = 'material_menu'
        reply_keyboard = build_course_keyboard('second_course')
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif "رجوع" in text:
        await start(update, context)
    else:
        await update.message.reply_text("الرجاء اختيار أحد الكورسات المتاحة.")

async def handle_material_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "رجوع" in text:
        current_stage = context.user_data.get('current_stage', 'first_stage')
        context.user_data['state'] = 'course_menu'
        if current_stage == 'first_stage':
            reply_keyboard = [
                ["🟧 First course 🟧"],
                ["⬛ Second course ⬛"],
                ["⬅️ رجوع إلى المراحل"]
            ]
        else:
            reply_keyboard = [
                ["🟧 First course 🟧"],
                ["⬅️ رجوع إلى المراحل"]
            ]
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text("تم الرجوع.", reply_markup=reply_markup)
        return

    context.user_data['current_material'] = text
    course_location = context.user_data.get('current_location', 'first_course')
    course_prefix = "first_stage_first_course" if course_location == 'first_course' else "first_stage_second_course"
    clean_name = clean_material_name(text)

    if text in MATERIALS_NO_PRACTICAL:
        context.user_data['last_section'] = "📖 نظري"
        context.user_data['skip_section_menu'] = True
        material_base = f"{course_prefix}_{clean_name}_نظري"
        numbers = get_available_lecture_numbers(material_base)
        if numbers:
            context.user_data['state'] = 'lecture_number_menu'
            reply_keyboard = build_lecture_keyboard(numbers)
            reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("📖 نظري", reply_markup=reply_markup)
        else:
            await update.message.reply_text("لا توجد محاضرات متاحة لهذه المادة حالياً.")
        return

    context.user_data['skip_section_menu'] = False
    context.user_data['state'] = 'section_menu'
    reply_keyboard = [
        ["📖 نظري"],
        ["🔬 عملي"],
        ["🔗 مصادر"],
        ["⬅️ رجوع"]
    ]
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def handle_section_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📖 نظري" or text == "🔬 عملي":
        context.user_data['last_section'] = text
        material_name_raw = context.user_data.get('current_material', '')
        course_location = context.user_data.get('current_location', 'first_course')
        course_prefix = "first_stage_first_course" if course_location == 'first_course' else "first_stage_second_course"
        clean_name = clean_material_name(material_name_raw)
        section = "نظري" if "نظري" in text else "عملي"
        material_base = f"{course_prefix}_{clean_name}_{section}"
        numbers = get_available_lecture_numbers(material_base)
        if numbers:
            context.user_data['state'] = 'lecture_number_menu'
            reply_keyboard = build_lecture_keyboard(numbers)
            reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(f"لا توجد محاضرات في قسم {section} حالياً.")
        return

    elif text == "🔗 مصادر":
        material_name_raw = context.user_data.get('current_material', '')
        course_location = context.user_data.get('current_location', 'first_course')
        course_prefix = "first_stage_first_course" if course_location == 'first_course' else "first_stage_second_course"
        clean_name = clean_material_name(material_name_raw)
        key = f"{course_prefix}_{clean_name}_مصادر"
        file_ids = LECTURE_FILE_IDS.get(key)
        if file_ids:
            caption = f"📚 {material_name_raw} - مصادر"
            await send_files_by_ids(update, context, file_ids, caption)
        else:
            await update.message.reply_text("📭 لا توجد مصادر مرفقة لهذه المادة.")
        return

    elif text == "⬅️ رجوع":
        context.user_data['state'] = 'material_menu'
        course_location = context.user_data.get('current_location', 'first_course')
        reply_keyboard = build_course_keyboard(course_location)
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
        await update.message.reply_text("تم الرجوع.", reply_markup=reply_markup)
    else:
        await update.message.reply_text("الرجاء اختيار نظري أو عملي.")

async def handle_lecture_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "⬅️ رجوع":
        if context.user_data.get('skip_section_menu'):
            context.user_data['state'] = 'material_menu'
            course_location = context.user_data.get('current_location', 'first_course')
            reply_keyboard = build_course_keyboard(course_location)
            reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("تم الرجوع.", reply_markup=reply_markup)
        else:
            context.user_data['state'] = 'section_menu'
            reply_keyboard = [
                ["📖 نظري"],
                ["🔬 عملي"],
                ["🔗 مصادر"],
                ["⬅️ رجوع"]
            ]
            reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("تم الرجوع.", reply_markup=reply_markup)
        return
    elif text == "🔝 القائمة الرئيسية":
        await start(update, context)
        return

    if not text.isdigit():
        await update.message.reply_text("الرجاء اختيار رقم محاضرة صحيح.")
        return

    material_name_raw = context.user_data.get('current_material', '')
    course_location = context.user_data.get('current_location', 'first_course')
    current_section_raw = context.user_data.get('last_section', '📖 نظري')
    course_prefix = "first_stage_first_course" if course_location == 'first_course' else "first_stage_second_course"
    clean_name = clean_material_name(material_name_raw)
    section = "عملي" if "عملي" in current_section_raw else "نظري"

    key = f"{course_prefix}_{clean_name}_{section}_{text}"
    file_ids = LECTURE_FILE_IDS.get(key)

    if file_ids:
        caption = f"{material_name_raw} - {current_section_raw} - محاضرة {text}"
        await send_files_by_ids(update, context, file_ids, caption)
    else:
        await update.message.reply_text("❌ المحاضرة غير متوفرة حالياً. تأكد من الرقم.")

async def main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state', 'main_menu')
    if state == 'main_menu':
        await handle_main_menu(update, context)
    elif state == 'course_menu':
        await handle_course_menu(update, context)
    elif state == 'material_menu':
        await handle_material_menu(update, context)
    elif state == 'section_menu':
        await handle_section_menu(update, context)
    elif state == 'lecture_number_menu':
        await handle_lecture_number(update, context)
    else:
        await start(update, context)

def main():
    TOKEN = os.environ.get("BOT_TOKEN", "8775418806:AAEoYvujCfTnJLxkFnQnY9k4w9iyfHJ7LA4")
    
    # بدء الخادم الوهمي في خيط منفصل
    threading.Thread(target=start_fake_server, daemon=True).start()
    
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(120)
        .read_timeout(120)
        .build()
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_handler))
    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()