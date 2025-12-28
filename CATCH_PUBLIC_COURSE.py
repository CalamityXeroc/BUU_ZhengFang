# ``
from bs4 import BeautifulSoup
import time
import MENU
import LOGIN
import os


class info:
    InitHeader = {
        "Host": "jwxt.buu.edu.cn",
        "Connection": "keep-alive",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 NetType/WIFI MicroMessenger/7.0.20.1781(0x6700143B) WindowsWechat(0x63090c11) XWEB/11581 Flue",
    }
    public_course_page_main = "https://jwxt.buu.edu.cn/xf_xsqxxxk.aspx"


class PublicCourse:
    def __init__(self, account: LOGIN.Account):
        self.account: LOGIN.Account = account
        self.course_list = []
        self.num_of_selected = 0
        self.num_of_courses = 0

    def get_public_page(self):
        url = (
            info.public_course_page_main
            + "?xh="
            + self.account.account_data["username"]
            + "&xm="
            + self.account.name
            + "&gnmkdm=N121109"
        ).encode("utf-8")
        header = info.InitHeader
        header["Referer"] = url
        response = self.account.session.get(url=url, headers=header)
        
        try:
            soup = BeautifulSoup(response.text, "lxml")
            viewstate = soup.find("input", type="hidden", id="__VIEWSTATE").get("value")
            viewstategenerator = soup.find("input", type="hidden", id="__VIEWSTATEGENERATOR").get("value")
            
            POSTData = {
                "ddl_ywyl": "",
                "__EVENTTARGET": "dpkcmcGrid$txtPageSize",
                "__VIEWSTATE": viewstate,
                "__VIEWSTATEGENERATOR": viewstategenerator,
                "dpkcmcGrid$txtChoosePage": "1",
                "dpkcmcGrid$txtPageSize": "200",
            }
            # Update headers for POST
            header["Content-Type"] = "application/x-www-form-urlencoded"
            response = self.account.session.post(url=url, data=POSTData, headers=header)
            print("------get_public_page success (PageSize=200)------")
        except Exception as e:
            print(f"------get_public_page pagination failed: {e}, using default page------")

        return response

    def get_the_message_of_page(self, response):
        self.course_list = [] # 清空列表，防止重复添加
        soup = BeautifulSoup(response.text, "lxml")
        links = soup.find_all("tr")

        valid_course_count = 0
        for num, link in enumerate(links[1:]):
            # num 是从 0 开始的索引，对应 links[1] (第一行数据)
            # 假设 ASP.NET 的 ctl 控件索引从 02 开始 (对应第一行数据)
            # 所以 ctl_index = num + 2
            ctl_index = str(num + 2).zfill(2)
            
            try:
                tds = link.find_all("td")
                # 根据用户反馈调整索引
                # 原索引: name=2, code=3, teacher=4, time=5, margin=11
                # 观测到: tds[4]=Name, tds[5]=Code, tds[11]=Time-like("02-10")
                
                name = tds[4].text.strip()
                code = tds[5].text.strip()
                teacher = tds[6].text.strip() # 猜测
                time = tds[11].text.strip()   # 用户反馈该位置显示类似时间的信息
                margin = tds[12].text.strip() # 猜测余量在时间之后

                if time == "校区":
                    continue
                
                valid_course_count += 1
                # 传入 ctl_index 以便后续抢课使用正确的控件ID
                lessen = PublicCourseInfo(valid_course_count, name, code, teacher, time, margin, ctl_index)
                self.course_list.append(lessen)
            except BaseException:
                continue

        return

    def catch_course(self, response):
        if not self.course_list:
            print("未找到任何课程信息，无法选课。")
            return

        while True:
            user_input = input("输入想要抢的课程编号(课程编号即为第一项序号)\n退出程序输入数字‘0’\n>>>")
            if user_input == '0':
                return
            if user_input.isdigit():
                n = int(user_input)
                if 1 <= n <= len(self.course_list):
                    break
            print("请输入正确的课程编号！")

        # 获取用户选择的课程对象
        selected_course = self.course_list[n - 1]
        # 获取该课程对应的真实控件索引
        ctl_index = selected_course.ctl_index
        
        url = (
            info.public_course_page_main
            + "?xh="
            + self.account.account_data["username"]
        )
        soup = BeautifulSoup(response.text, "lxml")
        header = LOGIN.ZUCC.InitHeader
        POSTData = {
            "__EVENTTARGET": "dpkcmcGrid$txtPageSize",
            "__VIEWSTATE": soup.find("input", type="hidden", id="__VIEWSTATE").get(
                "value"
            ),
            "__VIEWSTATEGENERATOR": soup.find(
                "input", type="hidden", id="__VIEWSTATEGENERATOR"
            ).get("value"),
            "dpkcmcGrid$txtChoosePage": "1",
            "dpkcmcGrid$txtPageSize": "200",
            "Button1": "立即提交",
        }
        # 使用正确的 ctl_index 构造 POST 数据
        POSTData["kcmcGrid$ctl" + ctl_index + "$xk"] = "on"
        POSTData["kcmcGrid$ctl" + ctl_index + "$jc"] = "on"
        
        import requests # 确保导入 requests
        
        while True:
            current_time = time.strftime("%H:%M:%S", time.localtime())
            print(f"[{current_time}] 正在尝试抢课: {selected_course.name}")
            
            try:
                # 设置超时时间为 5 秒，避免长时间等待
                response = self.account.session.post(url=url, headers=header, data=POSTData, timeout=5)
            except requests.exceptions.RequestException as e:
                print(f"[{current_time}] 请求超时或网络错误，正在重试... ({e})")
                continue

            if response.status_code != 200:
                print(f"[{current_time}] 服务器返回状态码 {response.status_code} (可能是502/503)，正在重试...")
                continue

            if self.num_of_selected_courses(response) == (self.num_of_selected + 1):
                print(
                    "抢课成功！"
                    + "\t\t"
                    + str(time.strftime("%m-%d-%H-%M-%S", time.localtime(time.time()))),
                    flush=True,
                )
                self.num_of_selected += 1
                return
            else:
                try:
                    reason = (
                        "错误原因："
                        + BeautifulSoup(response.text, "lxml")
                        .find("script")
                        .string.split("'")[1]
                    )
                except BaseException:
                    reason = "错误原因：未知或已抢课成功"
                print(
                    reason
                    + "\t\t"
                    + str(time.strftime("%m-%d-%H-%M-%S", time.localtime(time.time()))),
                    flush=True,
                )
            
            if os.path.exists("stop.txt"):
                print("检测到 stop.txt，停止抢课。")
                break

    def num_of_selected_courses(self, response):
        soup = BeautifulSoup(response.text, "lxml")
        links = soup.find_all("tr")
        number = 0
        for link in links[1:]:
            try:
                tds = link.find_all("td")
                tmp = tds[5].text
                number = number + 1
                if tmp == "校区":
                    number = 0
            except BaseException:
                break
        return number

    def search(self):
        search_dic = {"序号": "关键词类型", "1": "课程名称", "2": "教师", "3": "时间"}
        search_dic_menu = MENU.MENU(search_dic)
        search_dic_menu.print_list()
        n = input(">>>")
        key = input("输入查询信息：")
        if n == "1":
            for lesson in self.course_list:
                if key in lesson.name:
                    lesson.show_course_info()
        elif n == "2":
            for lesson in self.course_list:
                if key in lesson.teacher:
                    lesson.show_course_info()
        elif n == "3":
            for lesson in self.course_list:
                if key in lesson.time:
                    lesson.show_course_info()
        return

    def run(self):
        response = self.get_public_page()
        self.get_the_message_of_page(response)
        dic_of_public = {"1": "列出所有课表", "2": "按类型搜索内容", "0": "退出"}
        dic_of_public_menu = MENU.MENU(dic_of_public)
        dic_of_public_menu.print_list()
        while True:
            n = input(">>>")
            if n == "1":
                for lessen in self.course_list:
                    lessen.show_course_info()
                break
            elif n == "2":
                self.search()
                break
            elif n == "0":
                return
            print("请输入正确的序号")
        self.num_of_selected = self.num_of_selected_courses(response)
        print("已选课程数量：" + str(self.num_of_selected))
        self.catch_course(response)
        pass


class PublicCourseInfo:
    def __init__(self, num, name, code, teacher, time, margin, ctl_index):
        self.num = str(num)
        self.name = str(name)
        self.code = str(code)
        self.teacher = str(teacher)
        self.time = str(time)
        self.margin = str(margin)
        self.ctl_index = str(ctl_index)

    def show_course_info(self):
        print(
            "课程编号:"
            + self.num
            + "\t课程名称:"
            + self.name
            + "\t课程代码:"
            + self.code
            + "\t课程教师:"
            + self.teacher
            + "\t课程时间:"
            + self.time
            + "\t课程余量:"
            + self.margin
        )

    def __contains__(self, item):
        if item in self:
            return True
        else:
            return False
