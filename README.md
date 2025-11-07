# Stock-tracking
💰 三桶投资组合仪表板 (Three-Bucket Portfolio Dashboard)

这是一个基于 Streamlit 的个人投资仪表板，用于跟踪和管理"三桶投资策略"。

这个应用是交互式的，允许用户直接在浏览器中编辑持仓，并自动获取（股票/ETF）的实时价格来计算市值。

✨ 主要功能

三桶分离： 清晰地将持仓分为 "桶1 (核心)", "桶2 (收入)" 和 "桶3 (投机)"。

可交互编辑： 直接在网页表格中双击单元格来修改 ticker（代码）, quantity（数量）和 total_cost（总成本）。

动态行： 支持动态添加 (Add) 或删除 (Delete) 持仓行。

实时价格： 自动使用 yfinance 库获取股票和ETF的实时市场价格。

自动计算： 自动计算每个持仓的 "市值" (Market Value) 和 "浮动盈亏" (P/L)，并汇总到顶部的总览仪表板。

会话保持： 使用 st.session_state 来保存您的编辑，只要您不关闭浏览器选项卡，数据就会被保留。

🚀 如何在本地运行

这就是您刚才提问的 pip install 步骤的答案！

克隆或下载仓库：
将 app.py, requirements.txt 和 README.md 文件放在同一个文件夹中。

（可选，但强烈推荐）创建虚拟环境：

# For Mac/Linux
python3 -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
.\venv\Scripts\activate


安装所有依赖库：
在您的终端中，进入该文件夹，并运行以下命令。这将会读取 requirements.txt 文件并安装所有必需的库。

pip install -r requirements.txt


运行 Streamlit 应用：

streamlit run app.py


Streamlit 会自动在您的浏览器中打开一个新的页面，显示您的仪表板。

🖥️ 如何使用

编辑： 双击任何白色的单元格（如 ticker, quantity, total_cost）进行修改。按 Enter 键确认。

添加/删除： 选中一行按 Delete (或 Backspace) 键删除。点击表格底部的 + 号添加一个新行。

刷新价格： 点击底部的 "手动刷新实时价格" 按钮来强制清除缓存并获取最新股价。

注意： "现价", "市值", "浮动盈亏" 列是自动计算的，因此被设为只读（灰色）。

☁️ 如何部署到 Streamlit Cloud

确保 app.py 和 requirements.txt 都在您的 GitHub 仓库的根目录中。

登录 Streamlit Community Cloud。

点击 "New app" 并连接到您的 GitHub 仓库。

选择 app.py 作为主文件。

点击 "Deploy!"。
