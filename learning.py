# 字面量
# int
888
# float
13.14
# string
"坚持"
# bool
True
False
# NoneType
None
print("-------------------------------------------------")

# print
print(888)
print(13.14)
print("坚持")
print("Stick to it, and you'll succeed")
print("坚\n持")
print("""落魄谷中寒风吹，春秋蝉鸣少年归。

荡魂山处石人泪，定仙游走魔向北。

逆流河上万仙退，爱情不敌坚持泪。

宿命天成命中败，仙尊悔而我不悔。""")
num1 = 666
print("主人" + str(num1))
print("主人", num1)
master = "主人"
print(f"你好，{master}")
print("-------------------------------------------------")

# 注释
# 单行注释 多选注释command+/
"""
多
行
注
释
"""
print("-------------------------------------------------")

# 计算
print(1 + 2 - 2 * 4 / 2**2 + 1**3)
print(7 % 3)  # 求模运算符（余数）
import math

print(math.pi)
print(math.e)
print(math.sin(30))  # 识别弧度
print(math.sin(math.radians(30)))
print(math.degrees(math.acos(0.5)))
print(math.log2(4))
print(2**10)
print(math.pow(2, 10))
print(math.pow(1024, 1 / 10))
print(math.sqrt(4))
x = 3.7
print(math.ceil(x))  # 向上取整
print(math.floor(x))  # 向下取整
print(round(x))  # 四舍五入
a = -1
b = -2
c = 3
print((-b + math.sqrt(b**2 - 4 * a * c)) / (2 * a))
deta = math.pow(b, 2) - 4 * a * c
print((-b - math.pow(deta, 1 / 2)) / (2 * a))
print("-------------------------------------------------")

# 变量
money = 50
print("中午十二点钱包还有", money, "元")
money = money - 10
print("买了冰淇凌花费 10 元，还剩", money, "元")
print("下午一点，钱包还剩", money, "元")
print("买了巧克力花费 10 元")
money = money - 10
print("下午二点，钱包还剩", money, "元")
print("买了可乐花费 5 元")
money = money - 5
print("下午三点，钱包还剩", money, "元")
print("-------------------------------------------------")

# 数据类型
print(type(888))
print(type(13.14))
print(type("坚持"))
print(type(money))
print(type(False))
print(type(True))
print(type(None))
int_type = type(888)
float_type = type(13.14)
string_type = type("坚持")
print(int_type)
print(float_type)
print(string_type)
persist = "坚持"
persist_type = type(persist)
print(persist_type)
print("-------------------------------------------------")

# 转换
int_str = str(11)
print(type(int_str))
print(int_str)
float_str = str(1.1)
print(type(float_str))
print(float_str)
str_int = int("1")
print(type(str_int))
print(str_int)
str_float = float("1.11")
print(type(str_float))
print(str_float)
float_int = int(2.2)
print(type(float_int))
print(float_int)
int_float = float(2)
print(type(int_float))
print(int_float)
print("-------------------------------------------------")

# len
print(len("Hi!"))
print(len(" 6 "))
print(len("坚\n持"))
print(len('坚"持'))
print("-------------------------------------------------")

# 索引
print("12345"[0])
print("12345"[1])
print("12345"[-1])
# error print("12345"[5])
print("-------------------------------------------------")

# 交互模式
# 终端/控制台 无需print() 不保存
print("-------------------------------------------------")

# input
# user_weight = input("请输入您的体重（KG）:")
# user_height = input("请输入您的身高（M）:")
# user_BMI = float(user_weight)/(float(user_height)**2)
# print(f"您的BMI指数是:{user_BMI}")
# msg = "欢迎您的到来！"
# msg += "\n请输入您喜欢的电影："
# movie = input(msg)
# print(movie)
print("-------------------------------------------------")

# if
# mark = float(input("您的成绩为："))
# user_gender = input("您的性别是：")
# user_mark = "您的成绩为："
# if user_gender == "男":
#     if mark < 60:
#         print("先生，" + user_mark + "不及格")
#     elif 60 <= mark < 80:
#         print("先生，" + user_mark + "及格")
#     else:
#         print("先生，" + user_mark + "优秀")
# else:
#     if mark < 60:
#         print("女士，" + user_mark + "不及格")
#     elif 60 <= mark < 80:
#         print("女士，" + user_mark + "及格")
#     else:
#         print("女士，" + user_mark + "优秀")
fru = ["西瓜", "葡萄", "草莓", "橘子", "苹果"]
for item in fru:
    if item in ["西瓜", "橘子", "苹果"]:
        print("我爱吃" + item)
    else:
        print(item)
print("-------------------------------------------------")

# list
shopping_list = []
shopping_list.append("手机")
shopping_list.append("平板")
shopping_list.append("电脑")
shopping_list.append("电视")
shopping_list.append("游戏机")
shopping_list.append("键盘")
print(shopping_list)
shopping_list.remove("平板")
print(shopping_list)
del shopping_list[3]
print(shopping_list)
key_board = shopping_list.pop(3)
print(key_board)
print(shopping_list)
shopping_list[2] = "耳机"
print(shopping_list)
shopping_list.insert(2, "手表")
print(shopping_list)
print(shopping_list[0])
print(shopping_list[0:2])  # 切片
print(shopping_list[:2])
print(shopping_list[2:])
for item in shopping_list[0:2]:
    print(item)
print(shopping_list[::2])
print(shopping_list[1::2])
print(shopping_list[:])
price = [800, 600, 1000]
sorted_price = sorted(price)
max_price = max(price)
min_price = min(price)
print(max_price)
print(min_price)
print(sorted_price)
sorted_price.reverse()
print(sorted_price)
print(len(shopping_list))
print("-------------------------------------------------")

# 元组 tuple
t1 = ("春", "夏", "秋", "冬")
# error t1.append("四季")
t = ("a", "b", "c", "d", "e", "f", "g")
print(t[1:4])
print("-------------------------------------------------")

# for
names = ["张三", "李四", "王五"]
for name in names:
    print(name + "同学")
    print("------")
print("以上")
print("-------------------------------------------------")

# range
print(list(range(1, 10, 2)))
xx = list(range(1, 11))
print(xx)
print(max(xx))
print(min(xx))
print(sum(xx))
num = [n * 2 for n in range(1, 6)]
print(num)
nums = [1, 2, 3]
yy = [n * 2 for n in nums]
print(yy)
print("-------------------------------------------------")

# 布尔 bool
print(7 < 5)
print(7 > 5)
print(7 == 5)
print(7 != 5)
apple = "苹果"
print(apple == "苹果")
print(apple != "苹果")
print("a" > "b")  # 比较码点
print("A" > "a")
print(True and False)
print(True and True)
print(False and False)
print(True or False)
print(False or False)
print(not True)
print(not not True)
print(3 not in [3, 4, 5])
print(0)
"""
以下会被认为False
""     空字符串
0      数值零
None   空值
()     空元组
[]     空列表
{}     空字典
"""
print("-------------------------------------------------")

# dictionary
person_dict = {}
person_dict["name"] = "Jack sparrow"
person_dict["age"] = 100
person_dict["gender"] = "male"
print(person_dict)
del person_dict["gender"]
print(person_dict)
person_dict["age"] = 10
print(person_dict)
dict1 = {"bb": 22, "aa": 11, "cc": 33, "dd": 44}
for key, value in dict1.items():
    print(key, value)
for key, value in sorted(dict1.items()):
    print(key, value)
for key in dict1.keys():
    print(key)
for key in sorted(dict1.keys()):
    print(key, dict1[key])
for value in dict1.values():
    print(value)
p1 = {"name": "张三", "age": 18, "gender": "男"}
p2 = {"name": "李四", "age": 19, "gender": "女"}
p3 = {"name": "王五", "age": 20, "gender": "男"}
friends = [p1, p2, p3]
print(friends)
for f in friends:
    print(f["name"], f["age"], f["gender"])
person1 = {
    "name": "小明",
    "age": 18,
    "friends": ["小红", "小李", "小王"],
    "marks": {"语文": 100, "数学": 110, "英语": 120},
}
for key, value in person1.items():
    print(key, value)
print("-------------------------------------------------")

# 集合
dict2 = {"aa": 10, "bb": 20, "cc": 20, "dd": 10}
nums = set(dict2.values())
print(nums)
set1 = {1, 2, 2, 1}
print(set1)
print("-------------------------------------------------")

# %求模运算
# num = input("请输入数字：")
# if float(num) % 3 == 0:
#     print("您输入的数字是三的倍数")
# else:
#     print("您输入的数字不是三的倍数")
# num = input("请输入数字：")
# if float(num) % 2 == 0:
#     print("您输入的数字是偶数")
# else:
#     print("您输入的数字是奇数")
print("-------------------------------------------------")

# while循环
n = 0
while n < 5:
    print(n)
    n += 1
print("循环结束")
# msg = " "
# while msg != "q":
#     msg = input("请输入您的姓名：(输入q退出）")
#     if msg != "q":
#         print(f"您好，{msg}")
# active = True
# while active:
#     msg = input("请输入您的姓名：(输入q退出）")
#     if msg == "q":
#         active = False
#     else:
#         print(f"您好，{msg}")
n = 0
while n < 5:
    if n % 2 == 0:
        n += 1
        continue
    else:
        print(n)
        n += 1
n = 0
while n < 5:
    if n == 3:
        break
    else:
        print(n)
        n += 1
list1 = ["aa", "bb", "cc"]
list2 = []
while list1:
    msg = list1.pop(0)
    list2.append(msg.title())
print(list2)
pets = ["cat", "dog", "mouse", "cat"]
while "cat" in pets:
    pets.remove("cat")
print(pets)
# user = { }
# active = True
# while active:
#     name = input("请输入您的姓名：")
#     age = input("请输入您的年龄：")
#     user[name] = int(age)
#     reply = input("保存成功，是否退出(y|n)")
#     if reply == "y":
#         active = False
# print(user)
print("-------------------------------------------------")


# def
def greet_user():
    print("hello world")
    print("I'm in greet_user")


greet_user()


def say(name, score1, score2):
    print(f"{name}同学")
    print(f"你的总成绩为{score1 + score2}")


say("张三", 1, 1)


def say(name="张三"):
    print(f"你好{name}")


say()
say("李四")


def say(name, friends=[]):
    friends.append(name)
    print(friends)


say("张三")
say("李四")


def say(name, friends=None):
    if friends == None:
        friends = []
    friends.append(name)
    print(friends)


say("张三")
say("李四")


def say(name, score1, score2):
    print(f"{name}同学")
    print(f"你的总成绩为{score1 + score2}")


say(score2=1, score1=1, name="张三")

x = 10


def foo(y):
    y += 1
    print(y)


foo(x)
print(x)

x = [10, 20, 30]


def foo(y):
    y[0] += 1
    print(y)


foo(x)
print(x)

x = [10, 20, 30]


def foo(y):
    y[0] += 1
    print(y)


foo(x[:])
print(x)
print(x[:])
print("-------------------------------------------------")


# * 元组
def sum1(*args):
    num = 0
    for item in args:
        num += item
    print(f"所求合为：{num}")


sum1(10, 20)


def sum1(*args):
    num = sum(args)
    print(f"所求合为：{num}")


sum1(10, 20)
print("-------------------------------------------------")


# ** 字典
def foo(**args):
    print(args)


foo(name="张三", age=18, gender="男")


def foo(**args):
    for k, v in args.items():
        print(f"键：{k}", f"值：{v}")


foo(name="张三", age=18, gender="男")
print("-------------------------------------------------")


# 函数返回值
def foo(a, b):
    return a + b


res = foo(1, 2)
print(res)
print("-------------------------------------------------")


# 变量作用域
def foo():
    n = 123  # 局部变量


foo()
print(n)

n = 123  # 全局变量


def foo():
    print(n)


foo()
print(n)

n = 123  # 全局变量


def foo():
    n = 100  # 新定义局部变量
    print(n)


foo()
print(n)

n = 123  # 全局变量


def foo():
    global n  # 引用全局变量
    n = 100
    print(n)


foo()
print(n)

n = 123  # 全局变量


def foo(n):  # 形参
    n += 1
    print(n)


foo(n)
print(n)
print("-------------------------------------------------")

# 模块
import tools1

tools1.foo1()
tools1.foo2()
tools1.foo3()

from tools2 import foo4 as f4, foo5 as f5, foo6 as f6

f4()
f5()
f6()

if __name__ == "__main__":  # 主文件判断
    print("这是主文件")
print("-------------------------------------------------")


# 对象和类
class Student:
    def __init__(self, a, b, c, d):
        self.name = a
        self.gender = b
        self.age = c
        self.height = d

    def listen(self):
        print("听课")

    def write(self):
        print("写作")


stu1 = Student(1, 2, 3, 4)
print(stu1.name)
stu1.listen()
del stu1.name
print(stu1.gender)
stu1.name = 1
print("-------------------------------------------------")


# 私有属性
class Person:
    def __init__(self, a):
        self.__age = a

    def get_age(self):
        return self.__age

    def set_age(self, b):
        if b in range(1, 100):
            self.__age = b
            print("修改成功")

        else:
            print("年龄错误")


per1 = Person(10)
print(per1.get_age())
per1.set_age(20)
print(per1.get_age())
per1.set_age(100)
print("-------------------------------------------------")


# 装饰器
def decorator(fuction):  # 无参数
    def x():
        print("准备执行")
        fuction()
        print("执行结束")

    return x


@decorator
def send_ms():
    print("发送短信")


send_ms()


def decorator1(func):  # 有参数
    def x(*args, **kwargs):
        print("准备执行")
        func(*args, **kwargs)
        print("执行结束")

    return x


@decorator1
def send_wechat(message):
    print(f"发送{message}")


@decorator1
def send_qq(name, message):
    print(f"给{name}发送{message}")


send_wechat(1)
send_qq(1, 2)


def decorator2(func):  # 有参数，有返回值
    def x(*args, **kwargs):
        print("准备执行")
        value = func(*args, **kwargs)
        print("执行结束")
        return value

    return x


@decorator2
def handsome():
    print("我好帅")
    return "0v0"


print(handsome())


class Person:
    def __init__(self, a):
        self.__age = a

    @property
    def age(self):
        return self.__age

    @age.setter
    def age(self, b):
        if b in range(1, 100):
            self.__age = b
            print("修改成功")

        else:
            print("年龄错误")

    @age.deleter
    def age(self):
        del self.__age
        print("删除了age属性")


per1 = Person(10)
print(per1.age)
per1.age = 20
print(per1.age)
per1.age = 100
del per1.age


class Age:  # 计算属性
    def __init__(self, x):
        self.__age = x

    @property
    def birth_year(self):
        return 2026 - self.__age


age1 = Age(18)
print(age1.birth_year)
print("-------------------------------------------------")


# 君子协定 + 改名机制
class 类名:
    def __init__(self, x):
        self.__age = x


对象 = 类名(18)
print(对象)
print(vars(对象))  # vars()查看属性
print(对象._类名__age)  # 改名机制，非严格私有
print("-------------------------------------------------")


# 继承
class A:  # 父类
    def __init__(self, a, b):
        self.name = a
        self.age = b

    def foo1(self):
        pass

    def foo2(self):
        pass


class B(A):  # 子类
    def foo1(self):
        print(f"姓名为{self.name}")


a1 = A(1, 2)
a1.foo1()
b1 = B(1, 2)
b1.foo1()


class A:  # 父类
    def __init__(self, a):
        if a == 1:
            print("账号错误")

        elif a == 2:
            print("密码错误")

        else:
            print("未知错误")


class B(A):  # 子类
    def __init__(self, a):
        if a == 3:
            print("验证码错误")

        else:
            super().__init__(a)  # super().转到给父类代理对象
            # A.__init__(self,a)         #父类.直接调用父类


B(1)
B(2)
B(3)
print("-------------------------------------------------")


# 组合与多态
class Hero:
    def q(self):
        pass

    def w(self):
        pass


class Ashe(Hero):  # 继承
    def q(self):
        print("艾希使用技能q")

    def w(self):
        print("艾希使用技能w")


class Gailun(Hero):  # 继承
    def q(self):
        print("盖伦使用技能q")

    def w(self):
        print("盖伦使用技能w")


class Player:
    def __init__(self, hero):
        self.hero = hero  # 组合

    def use_q(self):
        self.hero.q()  # 多态

    def use_w(self):
        self.hero.w()  # 多态


p1 = Player(
    Ashe()
)  # 对象(Ashe( )) 作为 实参 传入 类(Player) 的 方法(__init__) 的 形参(hero) 同时 p1 成为 类(Player) 的 对象
# p1.hero = hero                              把 类(Ashe) 的 对象(Ashe( )) 存进 类(Player) 的 对象(p1) 的 属性(hero)
p1.use_q()  # 对象(p1) 使用 类(Player) 的 方法(use_q)
"""
p1.hero.q( )                               类(Player) 的 对象(p1) 的 属性(hero) 实则为 类(Ashe) 的 对象(Ashe( ))
                                           p1.hero.q( ) 实则为 类(Ashe) 的 对象(Ashe( )) 内部执行 方法(q( ))
"""
