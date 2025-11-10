
	2. Read the user's "intent" from the intent attribute in user_info. 
	•	Example: “I’m a VC looking to talk about early-stage startups, talent recruitment, founders raising pre-seed.”
	•	Build a set of seed keywords + phrases: e.g., “pre-seed raise”, “hiring first engineering team startup”, “looking for VC”, “early stage startup recruiting” etc.

	3.	search the queries and the accounts in user_info.

	5.	use an openAI call to determine if the result matches the intent 

	6.	If so, add to the user's tweets.json.