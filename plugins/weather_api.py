import requests


def get_weather(city_name):
    url = f'https://apis.juhe.cn/simpleWeather/query?key=50a3bd415158e186903d6e6994157589&city={city_name}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['reason'] == '查询成功!':
            return data['result']
        else:
            return {"error": "查询失败: " + data['reason']}
    else:
        return {"error": "请求失败，状态码: " + str(response.status_code)}


def get_dressing_advice(temp):
    try:
        temp = float(temp)
    except ValueError:
        return "无法解析温度，无法提供穿衣建议。"

    if temp > 28:
        return "穿衣建议（一级 - 炎热）：轻棉织物短衣、短裙、薄短裙、短裤"
    elif 24.0 <= temp <= 27.9:
        return "穿衣建议（二级 - 热舒适）：棉麻面料衬衫、薄长裙、薄T恤"
    elif 21.0 <= temp <= 23.9:
        return "穿衣建议（三级 - 舒适）：棉麻短套装、T恤、薄牛仔、休闲服、职业套装"
    elif 18.0 <= temp <= 20.9:
        return "穿衣建议（四级 - 凉舒适）：套装、夹衣、风衣、夹克、西装、薄毛衣"
    elif 15.0 <= temp <= 17.9:
        return "穿衣建议（五级 - 温凉）：风衣、大衣、夹大衣、毛衣、西装、防寒服"
    elif 11.0 <= temp <= 14.9:
        return "穿衣建议（六级 - 凉）：毛衣、风衣、毛套装、西服套装"
    elif 6.0 <= temp <= 10.9:
        return "穿衣建议（七级 - 冷）：棉衣、冬大衣、皮夹克、厚呢外套、呢帽、手套、羽绒服"
    elif temp < 6.0:
        return "穿衣建议（八级 - 寒冷）：棉衣、冬大衣、皮夹克、厚呢外套、呢帽、手套、羽绒服"
    else:
        return "暂无穿衣建议"


def format_weather(city_name):
    weather_data = get_weather(city_name)

    if 'error' in weather_data:
        return weather_data['error']

    realtime = weather_data.get('realtime', {})
    if not isinstance(realtime, dict):
        return "天气数据格式错误，无法解析实时天气信息。"
    temp = realtime.get('temperature', '未知')
    info = realtime.get('info', '未知')
    humidity = realtime.get('humidity', '未知')
    direct = realtime.get('direct', '未知')
    power = realtime.get('power', '未知')
    aqi = realtime.get('aqi', '未知')

    result = (
        f"实时天气:\n"
        f"{info}, 温度: {temp}℃, 湿度: {humidity}%, "
        f"风向: {direct}, 风力: {power}级, AQI: {aqi}"
    )

    advice = get_dressing_advice(temp)
    result += f"\n\n{advice}"

    result += "\n\n未来几天的天气:"
    for day in weather_data.get('future', []):
        if isinstance(day, dict):
            date = day.get('date', '未知')
            weather = day.get('weather', '未知')
            temperature = day.get('temperature', '未知')
            wind = day.get('direct', '未知')
        elif isinstance(day, str):
            # If day is a string, try to parse it as a dictionary if possible
            try:
                import json
                day_dict = json.loads(day)
                date = day_dict.get('date', '未知')
                weather = day_dict.get('weather', '未知')
                temperature = day_dict.get('temperature', '未知')
                wind = day_dict.get('direct', '未知')
            except Exception:
                date = weather = temperature = wind = '未知'
        else:
            date = weather = temperature = wind = '未知'
        result += (
            f"\n日期: {date}, 天气: {weather}, 温度: {temperature}, 风向: {wind}"
        )
    return result
