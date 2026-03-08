1. Download Env Vars
2. Update ssl_verify
Add this to your bedrock.rb file
config/initializers/bedrock.rb Line 3-5
3. Enable bedrock in config
Modify your bedrock.yml
app/config/bedrock.yml line 2
4. Run the app with aws-vault
aws-vault exec loanos-staging -- chamber export -f dotenv pr-app pr-515 >
.env
Remove QUEUE_DATABASE_URL
Remove REDIS_HOST
Remove DATABASE_URL
if Rails.env.development?
 Aws.config.update(ssl_verify_peer: false)
end
enabled: true
aws-vault exec loanos-staging -- ./bin/dev