import LOGIN
from bs4 import BeautifulSoup
import time
import re
import os

class PlannedCourse:
    def __init__(self, account):
        self.account = account
        # 最终选择的课程种类的url
        self.obj_url = ""
        # 所有课程种类的url
        self.urls = []
        # 所有开课信息
        self.course_list = []
        # 发送选课数据包的时候要用到
        self.obj_viewstate = ""

    def enter_planned_course(self):
        url = LOGIN.ZUCC.PlanCourageURL + "?xh=" + self.account.account_data["username"]
        header = LOGIN.ZUCC.InitHeader
        header["Referer"] = url
        
        max_retries = 5
        for i in range(max_retries):
            try:
                # 获取选课页面
                response = self.account.session.get(url=url, headers=header)
                
                # 使用BeautifulSoup解析页面
                soup = BeautifulSoup(response.text, 'lxml')
                
                # 1. 提取专业名称
                zymc_input = soup.find('input', {'name': 'zymc'})
                if zymc_input:
                    zymc_value = zymc_input.get('value', '')
                    print("提取到专业名称:", zymc_value)
                    break # 成功找到，跳出重试循环
                else:
                    print(f"未找到专业名称输入框 (尝试 {i+1}/{max_retries})")
                    if i < max_retries - 1:
                        time.sleep(1)
            except Exception as e:
                print(f"获取选课页面出错: {e} (尝试 {i+1}/{max_retries})")
                if i < max_retries - 1:
                    time.sleep(1)
        else:
            # 循环结束仍未找到
            print("多次尝试仍未找到专业名称，可能是服务器繁忙或页面结构改变。")
            return None

        # 2. 构造POST请求参数

        # 2. 构造POST请求参数
        post_data = {
            'zymc': zymc_value,         # 专业名称
            'Button5': '本专业选课',     # 触发按钮
            'xx': '',                    # 通常为年级信息（留空）
            'txtPjUrl': '',              # 可选课程路径（留空）
        }
        
        # 添加必要的ASP.NET隐藏字段
        hidden_fields = soup.find_all('input', type='hidden')
        for field in hidden_fields:
            name = field.get('name', '')
            value = field.get('value', '')
            if name:  # 只添加有名称的字段
                post_data[name] = value

        # 3. 提交选课请求
        submit_url = url  # POST目标地址（同当前页面）
        response = self.account.session.post(
            url=submit_url,
            headers=header,
            data=post_data
        )

        print("选课请求提交状态:", response.status_code)
        return response


    def catch_course(self):
        for info in self.course_list:
            info.show_course_info()
        
        if not self.course_list:
            print("未找到任何课程信息，无法选课。")
            return

        while True:
            n = input(f"请输入要抢的班级编号 (1-{len(self.course_list)}，输入0退出)：")
            if n == "0":
                return
            elif not n.isdigit() or int(n) < 0 or int(n) > len(self.course_list):
                print(f"输入错误！请输入 1 到 {len(self.course_list)} 之间的数字。")
            else:
                break

        post_data = {"__EVENTTARGET": "Button1",
                     "__VIEWSTATEGENERATOR": "55DF6E88",
                     "xkkh": self.course_list[int(n) - 1].code,
                     "__VIEWSTATE": self.obj_viewstate,
                     "RadioButtonList1": 0}
        while True:
            header = LOGIN.ZUCC.InitHeader
            header["Referer"] = self.obj_url
            
            try:
                response = self.account.session.post(url=self.obj_url,headers=header, data=post_data)
            except Exception as e:
                print(f"抢课请求发送失败: {e}，正在重试...")
                time.sleep(1)
                continue

            soup = BeautifulSoup(response.text, "lxml")
            try:
                script_tags = soup.find_all('script')
                for script in script_tags:
                    if script.string:
                        match = re.search(r"alert\('([^']+)'\);", script.string)
                        if match:
                            reply = match.group(1)
            except AttributeError as e:
                reply = "属性访问错误：" + str(e)
            except ValueError as e:
                reply = str(e)
            except Exception as e:
                reply = "其他未知错误：" + str(e)
            
            # 增加对“已选”状态的判断
            if "一门课程不能选择两个班级" in reply or "上课时间冲突" in reply:
                print(f"\033[1;33m提示：{reply} (可能已选过该课程)\033[0m")
                return # 既然选过了，就直接退出抢课循环

            print(reply + "\t\t" + str(time.strftime('%m-%d-%H-%M-%S', time.localtime(time.time()))),flush=True)
            
            if os.path.exists("stop.txt"):
                print("检测到 stop.txt，停止抢课。")
                break
            
            if reply == "选课成功！":
                return
            if reply == "选课成功！":
                return

    def choose_course_class(self, response):
        self.account.soup = BeautifulSoup(response.text, "lxml")
        links = self.account.soup.find_all(name="tr")
        for num, link in enumerate(links[1:-1]):
            tds = link.find_all("td")
            print("编号：" + str(num + 1) + "\t课程名称: " + tds[1].text)
            url = "https://" + LOGIN.ZUCC.DOMAIN + "/clsPage/xsxjs.aspx?" + "xkkh=" + \
                  tds[1].find("a").get("onclick").split("=")[1][0:-3] + "&xh=" + self.account.account_data["username"]
            # print(url)
            self.urls.append(url)

        n = input("输入编号：")
        url = self.urls[int(n) - 1]
        self.obj_url = url
        header = LOGIN.ZUCC.InitHeader
        header["Referer"] = "https://jwxt.buu.edu.cn/xs_main.aspx?xh=" + self.account.account_data['username']
        
        # 增加重试机制
        max_retries = 10
        item_response = None
        for i in range(max_retries):
            try:
                item_response = self.account.session.get(url=url, headers=header)
                if item_response.ok:
                    break
                print(f"获取课程详情失败 (状态码 {item_response.status_code})，正在重试 ({i+1}/{max_retries})...")
                time.sleep(1)
            except Exception as e:
                print(f"获取课程详情出错: {e}，正在重试 ({i+1}/{max_retries})...")
                time.sleep(1)
        
        if item_response is None or not item_response.ok:
            print("多次尝试获取课程详情失败，请检查网络或稍后再试。")
            return

        # print(BeautifulSoup(item_response.text, 'lxml'))
        item_soup = BeautifulSoup(item_response.text, "lxml")
        self.obj_viewstate = item_soup.find_all(name='input', id="__VIEWSTATE")[0]["value"]
        item_trs = item_soup.find_all(name="tr")
        for num, item_tr in enumerate(item_trs[1:]):
            try:
                tds = item_tr.find_all("td")
                code = tds[0].find('input').get('value')
                teacher = tds[2].text
                time = tds[3].text
                lessen = PlannedCourseInfo(num + 1, code, teacher, time)
                self.course_list.append(lessen)
            except BaseException:
                return
        return

    def run(self):
        # 进入计划内选课界面
        response = self.enter_planned_course()
        if response is None:
            print("进入计划内选课界面失败，无法继续。")
            return
            
        # 爬取课程信息
        self.choose_course_class(response)
        # 模拟发包抢课
        self.catch_course()


class PlannedCourseInfo:
    def __init__(self, num, code, teacher, time):
        self.num = str(num)
        self.code = str(code)
        self.teacher = str(teacher)
        self.time = str(time)

    def show_course_info(self):
        print("课程编号:" + self.num
              + "\t课程代码:" + self.code
              + "\t课程教师:" + self.teacher
              + "\t课程时间:" + self.time)

    def __contains__(self, item):
        if item in self:
            return True
        else:
            return False


if __name__ == '__main__':
    account = LOGIN.Account()
    account.login()
    planned = PlannedCourse(account)
    planned.run()
