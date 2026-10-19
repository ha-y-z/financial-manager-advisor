Creating a new full-stack project implementing a financial manager and advisor. 
Its main tasks are: 
- To show a intuitive visualization of income and expenditure which is read from a CSV file.
  - Moreover, the transactions should be labeled in categories.
  - A database should be created to save already known labels and their related recipient/sender.
- Ingesting a pdf where the current portfolio is listed and creating a visualization (e.g. pie chart) of these investments.
Additional features are:
- Suggesting where the user can optimize/save his expenditure.
- Predicting/estimating when the user will reach his financial goal (e.g. buy real estate, financial independet) which is personally picked by the user.
- Giving the user a feedback to his investment portfolio like if its future save, which ones are risky or if he should sell or buy more.
  - A label could be added to each investment.
- Recommending new financial investements based on current ones.

The tech stack:
- Backend: Python with FastAPI, Langchain, HuggingFace + PyTorch
- Frontend: Vue.js with TypeScript, Vite
