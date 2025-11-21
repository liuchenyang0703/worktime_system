# 树图

│
├── config.py				# 数据库配置
├── worktime.py				# 主程序（启动此程序）
├── commute.sql				# 此程序所用的sql
├── README.md				# 程序说明
├── 部署方式.txt			# 部署方式（容器、非容器）
├── templates/
│   ├── admin.html          # 管理员主页面
│   ├── admin_users.html 	# 管理员用户管理页面
│   ├── change_pwd.html   	# 修改登录密码页面
│   ├── dashboard.html     	# 普通用户主页面
│   ├── login.html    		# 登陆页面
│   ├── profile.html   		# 普通用户个人中心页面
│   ├── profile_admin.html  # 管理员个人中心页面
│   ├── register.html 		# 注册账号页面
│   └── reset_pwd.html      # 忘记密码页面
└── static/
    ├── css/				# 页面样式调整css
    └── images/				# 图片存储路径


# 所需模块下载
pip3 install flask pymysql captcha python-dateutil -i https://mirrors.aliyun.com/pypi/simple/