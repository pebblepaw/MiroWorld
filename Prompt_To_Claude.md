# Front End

## Overall
- Can we have a light mode? I’ve received some feedback that current Dark mode can be a bit hard to read some text. Have a toggle on the bottom left corner to switch between the modes, it can be a sun/moon icon. #High
- Can we standardise and audit he font sizes? You can use the /frontend-skills/audit & /nothing-design skill. They suggest maybe 3-4 font size presets max. I noticed that the size of the text on different pages is not the same: 1. Screen 4's report body text is a bit too small; same for Screen 3 posts and comments 2. The page title “Analysis Report” is not the same font size as “Live Social Simulation”, some titles are in Capitals, some are not. 
- Can we also standardize the colour of the text, e.g. the "Analysis Questions" on page 1 should be in white so it stands out, similar labels on other screens like "Strategic Parameters" are already white. 
- Can we change the name of the project from “McKAInsey” to “MiroWorld”, I am scared of being sued by McKinsey for having too similar a name. MiroWorld is a reference to MiroFish, which has become very popular, and world cause we use Nemotron Data; I don't think MiroFish will sue? Let me know if you have any other ideas for a better name. We will need to find replace EVERYTHING in this project, we can just replace all I don't foresee any issues with that. 

## Screen 2
- What do you think of 500 agents? Is it too little or too much? Especially in relation to the number of simulation rounds. The maximum can be higher, maybe we can have the slider change colour, have it be green during a “recommended range”, and red otherwise. Suggest to me a number, then get me to confirm. 

## Screen 3
- Can we show number of likes/dislikes on the comments as well? If I'm not mistaken it's already a feature in OASIS. 
- The symbol for the like/dislike button seems to be different on Screen 5 compared to Screen 3, can we standardize and use Screen 5's one, it uses more color and stands out more. 
- For Simulation Rounds, 8 seems to be too little of a limit, I belive MiroFish's limit is around 70. We should proabbly set the maximum to be what we want the max of our paid plan to be, what is a reasonable number of rounds to have? 

## Screen 5
- I'm not sure if the number of likes on the comments are loading? It always seems to show 0. 
- Why does it the KOL viewpoint cards truncate and end with an ellipsis "..." (see the screenshot), can we make sure we show their whole viewpoint. 



# Backend

## Overall
- When I tried the USA dataset, I got an error "Knowledge artifact not found for session session-30006ebe". Fix this #High
- Name of the agents is still sometimes showing the place of residence. I understand the problem is currently that the dataset doesn’t have a column for names, so we use regex to parse from the Persona column. However, it is understandably not always the real name because of data cleanliness, and from empirical tests in these screenshots often it's parsing festival or planning area names. I think the current solution (not sure if it’s implemented correctly) is that during the very first checkpoint interview during the simulation (screen 3), the agent is asked what is their real name, and this updates the agent info in the backend. However, I see that some wrong names (festival names) are still showing on Screen 4 and 5, so we need to do more to tighten this data pipeline for the name. Can you check that the “asking the agent what their name is” step is implemented correctly during the simulation? If not, I have another idea: regex from several columns at once (maybe: travel_persona, sports_persona, persona, professional_persona, arts_persona), and take the majority winner. For the regex, some example of the data: “Esther is an…” or “Syed R. (Mogan) Lamaze is a cook” or sometimes it starts with an irrelevant detail like “At 48, John is”. The name is often the first one (or up to 7) capitalised words in a row, appearing at the start of the sentence, can include brackets for middle names, as long as it is sequential. For the data that don't start with the name, I think majority winner will fix this issue. 
- Can we put ALL the prompts in editable config files? I don’t want any of the prompts to be hard-coded, and this way I can manually tweak the prompts and run it a hundred times myself to see what phrasing works best. Especially all the prompts in Screen 3, 4 and 5. This means all the code files need to be referring to these config files, and not hard-coding it into the code. The config files should also be descriptive what each line does. #High 
- How come sometimes when I leave the tab in Chrome, go to another tab and come back after a while, it resets back to the onboarding page? #High 

## Screen 1 
- I manually tested the Product-Market-Fit screen, tried uploading a PDF but it did not work. Can we use the markitdown tool from microsoft: https://github.com/microsoft/markitdown I want at least these to work: PDF, PPT, Docx, images, HTML, text-based (CSV, MD, TXT). Most are already covered by the MarkItDown tool, we'd also have to edit the text descript on the upload card in the front-end. #High 
- After I uploaded a URL to a PDF file AirBnB, the scraped graph showed me complete nonsense output about "World Athletics Foundation", this is absolutely unacceptable, there should not be ANY fallback fake data anywhere in live mode. Can you thoroughly investigate why this happened, and remove these fallbacks? If it fails just show the correct error message please. #High
- Also, do you think the "campaign-content-testing" use case even really works? Because testing campaigns is a very visual thing, and I don't think any visual is passed to the simulated agents right? If I'm not mistaken only a summary of the data and certain text chunks from the lightRAG is passed to each agent. If so, I am okay to remove marketing as a feature entirely. Discuss with me, I want to hear your opinion #High

## Screen 2 
- In the "Strategic Parameters" card, a LLM is supposed to parse the user inputs, and convert it into either hard filters or "more of one demographic" filters. For example, user should be able to request for "more samples from planning area Bishan". I don't think it's currently working for anything other than the age parameter, which is hard-coded. It's fine if it's hard-coded to individual columns, but importantly it needs to work for every country's Nemotron Dataset. I understand there is a config for each country in /config/countries, if necessary we can add a section to the config for these filters, so at least it's config-based and not hard-coded in the code. #High

## Screen 3 
- Cost doesn’t seem accurate anymore, it’s not that high especially with Gemini, I believe the workflow was it should be based on 1. cached cost from the gemini websites 2. number of tokens output from the API call 
- Controversy Boost toggle state, approval rate & Net Sentiment does not seem to be persistent when I switch to another page and back. Rest of the content on the page is persistant. 
- Title of the post is still sometimes just the first sentence truncated. I thought we already ask the agent to generate a sensible title as part of the JSON output? 

## Screen 4
- Can the write-up for each analysis question be way longer and more insightful, did we set some kind of a limit, or is this an issue with the prompt? Would be easier to review this once ALL the prompts are in the /config folder, as mentioned above. #High

————————

# For the GitHub pages cache

## Overall
- After EVERYTHING above is fixed, regenerate the cache and push it back to github pages, I believe it's in it's own branch. 
- I want it such that on the onboarding screen, depending on which use case I click, it will show a different data uploaded, so e.g. if I click policy it will load the policy cache, Product Market Research will load the product cache. 
- For the Policy Use Case, use the cache in /Sample_Inputs/Policy/README.md, point number one. I also included a user question to add to the list of questions. For Product Market Research, use the /Sample_Inputs/Policy/Airbnb_Pitch_Example.md.
- Both Caches should use 100 agents, 20 rounds.

## Screen 3 
- Approval Rate & Net Sentiment didn't seem to be cached, both show 0. 

## Screen 4
- In the chat screen, it should pre-load questions asked about "Did any post change your mind"? 

