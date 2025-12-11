Music folder structure for AI Mood Detection Music Player

The app now uses mood-specific folders for better organization:

📁 Folder Structure:
├── happy/          - Place upbeat, cheerful songs here
├── sad/            - Place melancholic, slow songs here  
├── angry/          - Place intense, aggressive songs here
├── neutral/         - Place calm, ambient songs here (also fallback)
├── surprised/      - Place unexpected, surprising songs here
├── fearful/        - Place tense, anxious songs here
└── disgusted/       - Place harsh, unpleasant songs here

🎵 How it works:
1. The AI detects your facial expression (happy, sad, angry, etc.)
2. The app randomly selects a song from the corresponding mood folder
3. If a mood folder is empty, it falls back to the neutral folder
4. Songs are played automatically every 5 seconds based on detected mood

📝 Adding Songs:
- Drop MP3 files into the appropriate mood folder
- You can add multiple songs per mood (song1.mp3, song2.mp3, etc.)
- The app will randomly pick from available songs in that mood

⚠️ Note: Make sure to add at least one song to the neutral/ folder as it serves as fallback.


