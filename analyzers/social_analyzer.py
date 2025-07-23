# analyzers/social_analyzer.py
"""
Social media sentiment and community analysis for new tokens.
Analyzes Twitter, Telegram, and other social signals.
"""

import asyncio
import aiohttp
import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from models.token import SocialMetrics, TradingOpportunity
from utils.logger import logger_manager

class SocialAnalyzer:
    """
    Analyzes social media sentiment and community activity for new tokens.
    Provides insights into community strength and potential viral growth.
    """
    
    def __init__(self):
        """Initialize the social analyzer."""
        self.logger = logger_manager.get_logger("SocialAnalyzer")
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Social media patterns and keywords
        self.positive_keywords = [
            'moon', 'rocket', 'gem', 'bullish', 'pump', 'launch', 'early',
            'diamond', 'hands', 'hodl', 'buy', 'accumulate', 'breakout'
        ]
        
        self.negative_keywords = [
            'scam', 'rug', 'dump', 'bearish', 'sell', 'exit', 'avoid',
            'honeypot', 'fake', 'warning', 'careful', 'suspicious'
        ]
        
        self.viral_indicators = [
            'viral', 'trending', 'exploding', 'going crazy', 'massive',
            'everyone talking', 'blown up', 'unstoppable'
        ]
        
    async def initialize(self):
        """Initialize HTTP session for API calls."""
        timeout = aiohttp.ClientTimeout(total=20)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()
            self.session = None
            
    async def analyze_social_metrics(self, opportunity: TradingOpportunity) -> SocialMetrics:
        """
        Analyze social media sentiment and activity for a token.
        
        Args:
            opportunity: The trading opportunity to analyze
            
        Returns:
            SocialMetrics with sentiment and activity scores
        """
        self.logger.info(f"Analyzing social metrics: {opportunity.token.symbol}")
        
        metrics = SocialMetrics()
        
        try:
            # Extract token info
            token_symbol = opportunity.token.symbol
            token_name = getattr(opportunity.token, 'name', None)
            token_address = opportunity.token.address
            
            # Multiple analysis methods
            await self._analyze_twitter_mentions(token_symbol, token_name, metrics)
            await self._analyze_telegram_activity(token_symbol, token_address, metrics)
            await self._analyze_reddit_mentions(token_symbol, token_name, metrics)
            await self._check_influencer_mentions(token_symbol, metrics)
            
            # Calculate composite scores
            self._calculate_social_scores(metrics)
            
            self.logger.info(f"Social analysis complete: {token_symbol} - Score: {metrics.social_score:.2f}")
            
        except Exception as e:
            self.logger.error(f"Social analysis failed for {opportunity.token.symbol}: {e}")
            # Default to neutral scores
            metrics.social_score = 0.5
            metrics.sentiment_score = 0.0
            
        return metrics
        
    async def _analyze_twitter_mentions(self, symbol: str, name: Optional[str], metrics: SocialMetrics):
        """Analyze Twitter/X mentions and sentiment."""
        try:
            # Since Twitter API requires authentication, we'll use alternative methods
            # In a real implementation, you'd use Twitter API v2 or scraping tools
            
            # Placeholder for Twitter analysis
            # Would search for: $SYMBOL, token name, relevant hashtags
            # Would analyze: mention volume, sentiment, influencer engagement
            
            # Simulated Twitter metrics based on token characteristics
            if symbol and len(symbol) <= 5:  # Shorter symbols often get more attention
                estimated_mentions = 10
                metrics.twitter_followers = estimated_mentions * 50
            else:
                estimated_mentions = 3
                metrics.twitter_followers = estimated_mentions * 20
                
            self.logger.debug(f"Twitter analysis: {symbol} - {estimated_mentions} estimated mentions")
            
        except Exception as e:
            self.logger.debug(f"Twitter analysis failed: {e}")
            
    async def _analyze_telegram_activity(self, symbol: str, address: str, metrics: SocialMetrics):
        """Analyze Telegram group activity and membership."""
        try:
            if not self.session:
                return
                
            # Search for Telegram groups related to the token
            # This is a simplified approach - real implementation would use Telegram API
            
            # Check for common Telegram group naming patterns
            possible_groups = [
                f"{symbol.lower()}token",
                f"{symbol.lower()}coin", 
                f"official{symbol.lower()}",
                f"{symbol.lower()}community"
            ]
            
            # Placeholder for Telegram analysis
            # Would check: member count, activity level, admin responsiveness
            
            # Estimate based on symbol characteristics
            if len(symbol) <= 4:  # Short symbols often have active communities
                estimated_members = 500
            else:
                estimated_members = 100
                
            metrics.telegram_members = estimated_members
            self.logger.debug(f"Telegram analysis: {symbol} - {estimated_members} estimated members")
            
        except Exception as e:
            self.logger.debug(f"Telegram analysis failed: {e}")
            
    async def _analyze_reddit_mentions(self, symbol: str, name: Optional[str], metrics: SocialMetrics):
        """Analyze Reddit mentions and discussions."""
        try:
            if not self.session:
                return
                
            # Reddit analysis using public APIs or web scraping
            # Would check subreddits like: r/cryptocurrency, r/cryptomoonshots, etc.
            
            # Placeholder implementation
            reddit_score = 0.3  # Neutral baseline
            
            # Look for specific patterns that indicate Reddit activity
            if symbol and len(symbol) <= 5:
                reddit_score += 0.2
                
            metrics.reddit_subscribers = int(reddit_score * 1000)
            self.logger.debug(f"Reddit analysis: {symbol} - Score: {reddit_score}")
            
        except Exception as e:
            self.logger.debug(f"Reddit analysis failed: {e}")
            
    async def _check_influencer_mentions(self, symbol: str, metrics: SocialMetrics):
        """Check for mentions by crypto influencers."""
        try:
            # This would involve checking known crypto influencer accounts
            # Looking for mentions of the token symbol or contract address
            
            # Placeholder for influencer tracking
            # Real implementation would maintain a list of influential accounts
            # and monitor their posts for token mentions
            
            influencer_mentions = 0  # Default
            
            # Boost score if symbol has characteristics that influencers like
            if symbol and any(keyword in symbol.lower() for keyword in ['moon', 'safe', 'baby', 'doge']):
                influencer_mentions = 1
                
            metrics.sentiment_score += influencer_mentions * 0.3
            self.logger.debug(f"Influencer analysis: {symbol} - {influencer_mentions} mentions")
            
        except Exception as e:
            self.logger.debug(f"Influencer analysis failed: {e}")
            
    def _calculate_social_scores(self, metrics: SocialMetrics):
        """Calculate composite social and sentiment scores."""
        try:
            # Social activity score (0-1)
            activity_factors = []
            
            if metrics.twitter_followers:
                # Normalize Twitter followers (0-1, max at 10k followers)
                twitter_score = min(1.0, metrics.twitter_followers / 10000)
                activity_factors.append(twitter_score)
                
            if metrics.telegram_members:
                # Normalize Telegram members (0-1, max at 5k members)
                telegram_score = min(1.0, metrics.telegram_members / 5000)
                activity_factors.append(telegram_score)
                
            if metrics.reddit_subscribers:
                # Normalize Reddit activity (0-1, max at 2k)
                reddit_score = min(1.0, metrics.reddit_subscribers / 2000)
                activity_factors.append(reddit_score)
                
            # Calculate average social score
            if activity_factors:
                metrics.social_score = sum(activity_factors) / len(activity_factors)
            else:
                metrics.social_score = 0.3  # Default neutral score
                
            # Ensure sentiment score is in valid range
            metrics.sentiment_score = max(-1.0, min(1.0, metrics.sentiment_score))
            
            # If no sentiment was calculated, default to slightly positive
            if metrics.sentiment_score == 0.0:
                metrics.sentiment_score = 0.1
                
        except Exception as e:
            self.logger.error(f"Score calculation failed: {e}")
            metrics.social_score = 0.3
            metrics.sentiment_score = 0.0

    async def _analyze_twitter_mentions_real(self, symbol: str, name: Optional[str], metrics: SocialMetrics):
        """Real Twitter/X analysis using API."""
        try:
            # Requires Twitter API v2 Bearer Token
            headers = {"Authorization": f"Bearer {self.twitter_bearer_token}"}
            
            # Search for recent mentions
            query = f"({symbol} OR {name}) (crypto OR token OR launch) -is:retweet"
            url = "https://api.twitter.com/2/tweets/search/recent"
            
            params = {
                "query": query,
                "max_results": 100,
                "tweet.fields": "public_metrics,created_at,author_id",
                "user.fields": "public_metrics"
            }
            
            async with self.session.get(url, headers=headers, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    tweets = data.get('data', [])
                    
                    if tweets:
                        # Analyze sentiment and engagement
                        total_engagement = 0
                        positive_sentiment = 0
                        total_tweets = len(tweets)
                        
                        for tweet in tweets:
                            metrics_data = tweet.get('public_metrics', {})
                            engagement = (
                                metrics_data.get('like_count', 0) +
                                metrics_data.get('retweet_count', 0) * 2 +
                                metrics_data.get('reply_count', 0)
                            )
                            total_engagement += engagement
                            
                            # Simple sentiment analysis
                            text = tweet.get('text', '').lower()
                            if any(word in text for word in self.positive_keywords):
                                positive_sentiment += 1
                        
                        # Calculate metrics
                        avg_engagement = total_engagement / total_tweets if total_tweets > 0 else 0
                        sentiment_ratio = positive_sentiment / total_tweets if total_tweets > 0 else 0
                        
                        metrics.twitter_followers = int(avg_engagement * 10)  # Estimate
                        metrics.sentiment_score += (sentiment_ratio - 0.5) * 0.4  # -0.2 to +0.2
                        
                        self.logger.info(f"Twitter analysis: {symbol} - {total_tweets} tweets, avg engagement: {avg_engagement}")
                    
        except Exception as e:
            self.logger.debug(f"Twitter analysis failed: {e}")

    async def _analyze_telegram_real(self, symbol: str, token_address: str, metrics: SocialMetrics):
        """Real Telegram analysis using web scraping or APIs."""
        try:
            # Method 1: Search for official Telegram channels
            search_terms = [symbol, token_address[:8]]
            
            for term in search_terms:
                # Use Telegram search API or web scraping
                channels = await self._search_telegram_channels(term)
                
                for channel in channels:
                    # Verify it's the official channel
                    if await self._verify_official_channel(channel, token_address):
                        member_count = await self._get_telegram_member_count(channel)
                        recent_activity = await self._analyze_telegram_activity(channel)
                        
                        metrics.telegram_members = member_count
                        
                        # Analyze recent messages for sentiment
                        if recent_activity:
                            positive_messages = sum(1 for msg in recent_activity 
                                                if any(word in msg.lower() for word in self.positive_keywords))
                            total_messages = len(recent_activity)
                            
                            if total_messages > 0:
                                sentiment = (positive_messages / total_messages - 0.5) * 0.3
                                metrics.sentiment_score += sentiment
                        
                        break
                        
        except Exception as e:
            self.logger.debug(f"Telegram analysis failed: {e}")

    async def _analyze_reddit_real(self, symbol: str, name: Optional[str], metrics: SocialMetrics):
        """Real Reddit analysis using PRAW or API."""
        try:
            # Use Reddit API or PRAW
            subreddits = ['CryptoMoonShots', 'SatoshiStreetBets', 'altcoin', 'cryptocurrency']
            
            total_mentions = 0
            positive_mentions = 0
            
            for subreddit in subreddits:
                # Search for token mentions in the last 24 hours
                posts = await self._search_reddit_posts(subreddit, symbol, hours=24)
                
                for post in posts:
                    total_mentions += 1
                    
                    # Analyze post sentiment
                    title_text = (post.get('title', '') + ' ' + post.get('selftext', '')).lower()
                    
                    positive_score = sum(1 for word in self.positive_keywords if word in title_text)
                    negative_score = sum(1 for word in self.negative_keywords if word in title_text)
                    
                    if positive_score > negative_score:
                        positive_mentions += 1
            
            if total_mentions > 0:
                metrics.reddit_subscribers = total_mentions * 50  # Estimate community size
                sentiment = (positive_mentions / total_mentions - 0.5) * 0.2
                metrics.sentiment_score += sentiment
                
                self.logger.info(f"Reddit analysis: {symbol} - {total_mentions} mentions, {positive_mentions} positive")
            
        except Exception as e:
            self.logger.debug(f"Reddit analysis failed: {e}")

    async def _check_influencer_mentions_real(self, symbol: str, metrics: SocialMetrics):
        """Check real crypto influencer mentions."""
        try:
            # List of known crypto influencers (Twitter handles)
            influencers = [
                "elonmusk", "VitalikButerin", "aantonop", "SatoshiLite",
                "APompliano", "DocumentingBTC", "WClementeIII"
                # Add more influencer handles
            ]
            
            mentions_found = 0
            total_followers = 0
            
            for influencer in influencers:
                try:
                    # Check their recent tweets for token mentions
                    tweets = await self._get_user_tweets(influencer, count=50)
                    
                    for tweet in tweets:
                        if symbol.lower() in tweet.get('text', '').lower():
                            mentions_found += 1
                            
                            # Get influencer's follower count for weighting
                            user_data = await self._get_twitter_user_data(influencer)
                            followers = user_data.get('followers_count', 0)
                            total_followers += followers
                            
                            self.logger.info(f"Influencer mention: {influencer} ({followers:,} followers)")
                            
                except:
                    continue
            
            if mentions_found > 0:
                # Weight influence by follower count
                avg_followers = total_followers / mentions_found
                influence_score = min(0.5, (avg_followers / 1000000) * 0.3)  # Cap at 0.5
                
                metrics.sentiment_score += influence_score
                metrics.social_score += 0.2  # Bonus for influencer attention
                
                self.logger.info(f"Influencer analysis: {mentions_found} mentions, avg {avg_followers:,.0f} followers")
            
        except Exception as e:
            self.logger.debug(f"Influencer analysis failed: {e}")

    def _calculate_social_scores_enhanced(self, metrics: SocialMetrics):
        """Enhanced social score calculation with real data."""
        try:
            # Social activity score (0-1) based on multiple factors
            activity_factors = []
            
            # Twitter factor
            if metrics.twitter_followers:
                twitter_score = min(1.0, metrics.twitter_followers / 10000)
                activity_factors.append(twitter_score * 0.4)  # 40% weight
            
            # Telegram factor  
            if metrics.telegram_members:
                telegram_score = min(1.0, metrics.telegram_members / 5000)
                activity_factors.append(telegram_score * 0.4)  # 40% weight
            
            # Reddit factor
            if metrics.reddit_subscribers:
                reddit_score = min(1.0, metrics.reddit_subscribers / 2000)
                activity_factors.append(reddit_score * 0.2)  # 20% weight
            
            # Calculate weighted average
            if activity_factors:
                metrics.social_score = sum(activity_factors)
            else:
                metrics.social_score = 0.1  # Very low if no social presence
            
            # Sentiment bounds checking
            metrics.sentiment_score = max(-1.0, min(1.0, metrics.sentiment_score))
            
            # Boost overall score for very positive sentiment
            if metrics.sentiment_score > 0.3:
                metrics.social_score *= 1.2  # 20% boost for positive sentiment
            elif metrics.sentiment_score < -0.3:
                metrics.social_score *= 0.7  # 30% penalty for negative sentiment
            
            # Final bounds
            metrics.social_score = max(0.0, min(1.0, metrics.social_score))
            
        except Exception as e:
            self.logger.error(f"Enhanced score calculation failed: {e}")
            metrics.social_score = 0.3
            metrics.sentiment_score = 0.0