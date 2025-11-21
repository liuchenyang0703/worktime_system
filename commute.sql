-- 数据库：worktime_db
-- 描述：上下班打卡系统用户与记录表初始化脚本
-- 创建人：系统管理员
-- 创建日期：2025-10-17

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL COMMENT '用户展示名称',
    username VARCHAR(50) UNIQUE NOT NULL COMMENT '登录账号',
    password VARCHAR(255) NOT NULL COMMENT '登录密码',
    role ENUM('admin', 'user') DEFAULT 'user' COMMENT '角色：admin管理员，user普通用户'
) COMMENT='用户表';

-- 打卡记录表
CREATE TABLE IF NOT EXISTS records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '用户ID',
    date DATE NOT NULL COMMENT '打卡日期',
    clock_in TIME DEFAULT NULL COMMENT '上班时间',
    clock_out TIME DEFAULT NULL COMMENT '下班时间',
    work_hours DECIMAL(4,2) DEFAULT NULL COMMENT '工作时长（小时）',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) COMMENT='打卡记录表';

-- 插入默认管理员（默认账号：admin，密码：admin123）
INSERT IGNORE INTO users (display_name, username, password, role) VALUES
('系统管理员', 'admin', 'admin123', 'admin');