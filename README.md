# Under Pressure dashboard

This is the self-contained version of the SupeRR Selector dashboard. It includes the code, theme and final scored datasets needed to run the app online.

## Publish it as a URL

1. Create a new **public GitHub repository** called `superr-selector-dashboard`.
2. Upload every item inside this `submission_dashboard` folder to that repository. Keep the folder structure unchanged, especially the `data` and `.streamlit` folders. The large ball-by-ball dataset is already compressed for web upload.
3. Go to [share.streamlit.io](https://share.streamlit.io/) and sign in with GitHub.
4. Choose **Create app**.
5. Select your GitHub repository and choose `streamlit_app.py` as the main file.
6. Click **Deploy**. Streamlit will create a link similar to `https://your-app-name.streamlit.app`.
7. Open the link in an incognito browser window. If it works there, copy that URL into your Round 1 submission.

## Local check

```bash
python3 -m streamlit run streamlit_app.py
```

The dashboard has four views: methodology, calculator, match explorer and final Top 10 rankings.

The calculator uses real cricket inputs: completed overs and balls, score, wickets, target for a chase, recent wickets and current dot-ball streak. It calculates the component percentages and the final Pressure Index automatically.
