# VHS tape for pinpoint-eda demo
# Run from project root: vhs docs/demo.tape

Output docs/images/demo.gif
Output docs/images/demo.mp4
Set Shell "bash"
Set Theme "Dracula"
Set Width 1400
Set Height 900
Set FontSize 15
Set Padding 20
Set TypingSpeed 20ms
Set PlaybackSpeed 2

# Setup env
Hide
Type "export PATH=$HOME/.local/bin:$PATH"
Enter
Type "export FORCE_COLOR=1"
Enter
Type "cd /Users/ranman/dev/caylent/customers/dynata/pinpoint-eda"
Enter
Type "clear"
Enter
Sleep 0.5s
Show

# Show version
Type "pinpoint-eda --version"
Enter
Sleep 1s

# Run the real scan
Type "pinpoint-eda scan --profile caylent-sso"
Enter
Sleep 45s
