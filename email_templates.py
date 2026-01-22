"""
Email templates for SendGrid notifications
"""


def get_marketplace_purchase_confirmation_email(buyer_name: str, product_title: str, price: float, seller_name: str, video_url: str = None) -> str:
    """Email template for marketplace purchase confirmation to buyer"""
    video_section = ""
    if video_url:
        video_section = f"""
                    <div style="margin: 30px 0; text-align: center;">
                        <a href="{video_url}"
                           style="display: inline-block; background-color: #D4FF4F; color: #000; padding: 16px 32px;
                                  text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
                            Download Your Video
                        </a>
                    </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Purchase Confirmation</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #000;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .email-wrapper {{
                background-color: #111;
                border-radius: 12px;
                overflow: hidden;
                border: 1px solid #333;
            }}
            .header {{
                background: linear-gradient(135deg, #1a1a1a 0%, #0a0a0a 100%);
                padding: 40px 20px;
                text-align: center;
                border-bottom: 1px solid #333;
            }}
            .header h1 {{
                font-size: 28px;
                margin-bottom: 10px;
                font-weight: 600;
                color: #D4FF4F;
            }}
            .header p {{
                font-size: 16px;
                color: #888;
            }}
            .content {{
                padding: 40px 30px;
                background-color: #111;
            }}
            .greeting {{
                font-size: 16px;
                margin-bottom: 20px;
                color: #fff;
            }}
            .message {{
                font-size: 15px;
                line-height: 1.8;
                color: #aaa;
                margin-bottom: 30px;
            }}
            .purchase-box {{
                background-color: #1a1a1a;
                border: 1px solid #333;
                padding: 25px;
                margin: 30px 0;
                border-radius: 8px;
            }}
            .purchase-box h2 {{
                color: #D4FF4F;
                font-size: 14px;
                text-transform: uppercase;
                margin-bottom: 20px;
                font-weight: 600;
                letter-spacing: 0.5px;
            }}
            .purchase-row {{
                display: flex;
                justify-content: space-between;
                padding: 12px 0;
                border-bottom: 1px solid #333;
                font-size: 14px;
            }}
            .purchase-row:last-child {{
                border-bottom: none;
            }}
            .purchase-label {{
                color: #888;
                font-weight: 500;
            }}
            .purchase-value {{
                color: #fff;
                font-weight: 600;
            }}
            .amount {{
                font-size: 28px;
                color: #D4FF4F;
                font-weight: 700;
                margin: 20px 0;
                text-align: center;
            }}
            .footer {{
                background-color: #0a0a0a;
                padding: 30px;
                text-align: center;
                border-top: 1px solid #333;
                font-size: 12px;
                color: #666;
            }}
            .footer p {{
                margin-bottom: 10px;
            }}
            .footer a {{
                color: #D4FF4F;
                text-decoration: none;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="email-wrapper">
                <div class="header">
                    <h1>✓ Purchase Confirmed!</h1>
                    <p>Thank you for your purchase on Reelzila</p>
                </div>

                <div class="content">
                    <p class="greeting">Hi {buyer_name},</p>

                    <p class="message">
                        Great news! Your purchase has been completed successfully. You now have access to your video.
                    </p>

                    <div class="purchase-box">
                        <h2>📦 Purchase Details</h2>

                        <div class="purchase-row">
                            <span class="purchase-label">Video:</span>
                            <span class="purchase-value">{product_title}</span>
                        </div>

                        <div class="purchase-row">
                            <span class="purchase-label">Seller:</span>
                            <span class="purchase-value">{seller_name}</span>
                        </div>

                        <div class="purchase-row">
                            <span class="purchase-label">Amount Paid:</span>
                            <span class="purchase-value" style="color: #D4FF4F;">€{price:.2f}</span>
                        </div>
                    </div>

                    {video_section}

                    <p class="message" style="margin-top: 30px;">
                        You can also access your purchased videos anytime from your
                        <a href="https://reelzila.studio/account" style="color: #D4FF4F;">account dashboard</a>.
                    </p>
                </div>

                <div class="footer">
                    <p><strong style="color: #D4FF4F;">reelzila</strong> - AI Video Generation Platform</p>
                    <p>Questions? Contact us at <a href="mailto:support@reelzila.studio">support@reelzila.studio</a></p>
                    <p style="margin-top: 15px;">© 2024 Reelzila. All rights reserved.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def get_payout_approved_email(seller_name: str, amount: float, account_holder: str) -> str:
    """Email template for payout approval notification"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payout Approved</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f9fafb;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .email-wrapper {{
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px 20px;
                text-align: center;
            }}
            .header h1 {{
                font-size: 28px;
                margin-bottom: 10px;
                font-weight: 600;
            }}
            .header p {{
                font-size: 16px;
                opacity: 0.9;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .greeting {{
                font-size: 16px;
                margin-bottom: 20px;
                color: #333;
            }}
            .message {{
                font-size: 15px;
                line-height: 1.8;
                color: #555;
                margin-bottom: 30px;
            }}
            .status-box {{
                background-color: #f0fdf4;
                border-left: 4px solid #22c55e;
                padding: 20px;
                margin: 30px 0;
                border-radius: 4px;
            }}
            .status-box h2 {{
                color: #16a34a;
                font-size: 14px;
                text-transform: uppercase;
                margin-bottom: 15px;
                font-weight: 600;
            }}
            .status-row {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                border-bottom: 1px solid #dcfce7;
                font-size: 14px;
            }}
            .status-row:last-child {{
                border-bottom: none;
            }}
            .status-label {{
                color: #666;
                font-weight: 500;
            }}
            .status-value {{
                color: #333;
                font-weight: 600;
            }}
            .amount {{
                font-size: 24px;
                color: #22c55e;
                font-weight: 700;
                margin: 10px 0;
            }}
            .next-steps {{
                background-color: #f3f4f6;
                padding: 20px;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .next-steps h3 {{
                font-size: 14px;
                font-weight: 600;
                margin-bottom: 10px;
                color: #333;
            }}
            .next-steps p {{
                font-size: 13px;
                color: #666;
                line-height: 1.6;
            }}
            .cta-button {{
                display: inline-block;
                background-color: #667eea;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 4px;
                font-weight: 600;
                margin-top: 20px;
                font-size: 14px;
            }}
            .cta-button:hover {{
                background-color: #5568d3;
            }}
            .footer {{
                background-color: #f9fafb;
                padding: 30px;
                text-align: center;
                border-top: 1px solid #e5e7eb;
                font-size: 12px;
                color: #999;
            }}
            .footer p {{
                margin-bottom: 10px;
            }}
            .footer a {{
                color: #667eea;
                text-decoration: none;
            }}
            .divider {{
                height: 1px;
                background-color: #e5e7eb;
                margin: 30px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="email-wrapper">
                <div class="header">
                    <h1>✓ Payout Approved</h1>
                    <p>Your withdrawal request has been approved</p>
                </div>

                <div class="content">
                    <div class="greeting">Hi {seller_name},</div>

                    <div class="message">
                        Great news! Your payout request has been approved and we're now processing your bank transfer.
                        You should receive the funds in your bank account within 2-5 business days.
                    </div>

                    <div class="status-box">
                        <h2>Payout Details</h2>
                        <div class="status-row">
                            <span class="status-label">Amount:</span>
                            <span class="status-value">€{amount:.2f}</span>
                        </div>
                        <div class="status-row">
                            <span class="status-label">Account Holder:</span>
                            <span class="status-value">{account_holder}</span>
                        </div>
                        <div class="status-row">
                            <span class="status-label">Status:</span>
                            <span class="status-value" style="color: #22c55e;">Approved</span>
                        </div>
                    </div>

                    <div class="next-steps">
                        <h3>What Happens Next?</h3>
                        <p>
                            1. We've approved your withdrawal request<br>
                            2. We're processing your bank transfer<br>
                            3. You'll receive the funds in your bank account within 2-5 business days<br>
                            4. Check your bank account for the deposit
                        </p>
                    </div>

                    <div class="divider"></div>

                    <div class="message" style="margin-bottom: 0;">
                        If you have any questions about your payout, please contact our support team.
                    </div>

                    <a href="https://reelzila.studio/account?tab=seller" class="cta-button">View My Account</a>
                </div>

                <div class="footer">
                    <p>© 2024 Reelzila. All rights reserved.</p>
                    <p>
                        <a href="https://reelzila.studio/privacy">Privacy Policy</a> |
                        <a href="https://reelzila.studio/terms">Terms of Service</a> |
                        <a href="https://reelzila.studio/contact">Support</a>
                    </p>
                    <p style="margin-top: 15px; color: #ccc;">
                        You received this email because you requested a payout on Reelzila
                    </p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def get_payout_completed_email(seller_name: str, amount: float) -> str:
    """Email template for payout completion notification"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payout Completed</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f9fafb;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .email-wrapper {{
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                color: white;
                padding: 40px 20px;
                text-align: center;
            }}
            .header h1 {{
                font-size: 28px;
                margin-bottom: 10px;
                font-weight: 600;
            }}
            .header .emoji {{
                font-size: 40px;
                margin-bottom: 10px;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .greeting {{
                font-size: 16px;
                margin-bottom: 20px;
                color: #333;
            }}
            .message {{
                font-size: 15px;
                line-height: 1.8;
                color: #555;
                margin-bottom: 30px;
            }}
            .success-box {{
                background-color: #f0fdf4;
                border: 2px solid #22c55e;
                padding: 25px;
                margin: 30px 0;
                border-radius: 8px;
                text-align: center;
            }}
            .amount {{
                font-size: 32px;
                color: #22c55e;
                font-weight: 700;
                margin: 15px 0;
            }}
            .success-text {{
                font-size: 14px;
                color: #16a34a;
                font-weight: 500;
            }}
            .details-box {{
                background-color: #f3f4f6;
                padding: 20px;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .details-row {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                font-size: 14px;
                border-bottom: 1px solid #e5e7eb;
            }}
            .details-row:last-child {{
                border-bottom: none;
            }}
            .details-label {{
                color: #666;
                font-weight: 500;
            }}
            .details-value {{
                color: #333;
                font-weight: 600;
            }}
            .cta-button {{
                display: inline-block;
                background-color: #10b981;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 4px;
                font-weight: 600;
                margin-top: 20px;
                font-size: 14px;
            }}
            .cta-button:hover {{
                background-color: #059669;
            }}
            .footer {{
                background-color: #f9fafb;
                padding: 30px;
                text-align: center;
                border-top: 1px solid #e5e7eb;
                font-size: 12px;
                color: #999;
            }}
            .footer p {{
                margin-bottom: 10px;
            }}
            .footer a {{
                color: #10b981;
                text-decoration: none;
            }}
            .divider {{
                height: 1px;
                background-color: #e5e7eb;
                margin: 30px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="email-wrapper">
                <div class="header">
                    <div class="emoji">✓</div>
                    <h1>Payout Completed!</h1>
                    <p>Your funds have been transferred</p>
                </div>

                <div class="content">
                    <div class="greeting">Hi {seller_name},</div>

                    <div class="message">
                        Excellent! Your payout has been completed and transferred to your bank account.
                        The funds should now be available in your account.
                    </div>

                    <div class="success-box">
                        <div class="success-text">Amount Transferred</div>
                        <div class="amount">€{amount:.2f}</div>
                        <div class="success-text">✓ Successfully Completed</div>
                    </div>

                    <div class="details-box">
                        <div class="details-row">
                            <span class="details-label">Status:</span>
                            <span class="details-value" style="color: #10b981;">Completed</span>
                        </div>
                        <div class="details-row">
                            <span class="details-label">Amount:</span>
                            <span class="details-value">€{amount:.2f}</span>
                        </div>
                        <div class="details-row">
                            <span class="details-label">Destination:</span>
                            <span class="details-value">Your Bank Account</span>
                        </div>
                    </div>

                    <div class="message" style="margin: 20px 0; padding: 15px; background-color: #f0fdf4; border-radius: 4px; border-left: 4px solid #22c55e;">
                        💡 <strong>Pro Tip:</strong> Keep earning! The more you sell, the more you can withdraw.
                        Upload more videos to your marketplace to increase your earnings.
                    </div>

                    <div class="divider"></div>

                    <a href="https://reelzila.studio/account?tab=seller" class="cta-button">View My Earnings</a>
                </div>

                <div class="footer">
                    <p>© 2024 Reelzila. All rights reserved.</p>
                    <p>
                        <a href="https://reelzila.studio/privacy">Privacy Policy</a> |
                        <a href="https://reelzila.studio/terms">Terms of Service</a> |
                        <a href="https://reelzila.studio/contact">Support</a>
                    </p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def get_payout_rejected_email(seller_name: str, amount: float) -> str:
    """Email template for payout rejection notification"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payout Rejected</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f9fafb;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .email-wrapper {{
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                color: white;
                padding: 40px 20px;
                text-align: center;
            }}
            .header h1 {{
                font-size: 28px;
                margin-bottom: 10px;
                font-weight: 600;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .greeting {{
                font-size: 16px;
                margin-bottom: 20px;
                color: #333;
            }}
            .message {{
                font-size: 15px;
                line-height: 1.8;
                color: #555;
                margin-bottom: 30px;
            }}
            .alert-box {{
                background-color: #fef2f2;
                border-left: 4px solid #ef4444;
                padding: 20px;
                margin: 30px 0;
                border-radius: 4px;
            }}
            .alert-box h2 {{
                color: #dc2626;
                font-size: 14px;
                text-transform: uppercase;
                margin-bottom: 15px;
                font-weight: 600;
            }}
            .alert-box p {{
                font-size: 14px;
                color: #666;
                line-height: 1.6;
            }}
            .details-box {{
                background-color: #f3f4f6;
                padding: 20px;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .details-row {{
                display: flex;
                justify-content: space-between;
                padding: 10px 0;
                font-size: 14px;
                border-bottom: 1px solid #e5e7eb;
            }}
            .details-row:last-child {{
                border-bottom: none;
            }}
            .details-label {{
                color: #666;
                font-weight: 500;
            }}
            .details-value {{
                color: #333;
                font-weight: 600;
            }}
            .next-steps {{
                background-color: #f0f9ff;
                padding: 20px;
                border-radius: 4px;
                border-left: 4px solid #3b82f6;
                margin: 20px 0;
            }}
            .next-steps h3 {{
                color: #1e40af;
                font-size: 14px;
                font-weight: 600;
                margin-bottom: 10px;
            }}
            .next-steps p {{
                font-size: 13px;
                color: #666;
                line-height: 1.6;
            }}
            .cta-button {{
                display: inline-block;
                background-color: #3b82f6;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 4px;
                font-weight: 600;
                margin-top: 20px;
                font-size: 14px;
            }}
            .cta-button:hover {{
                background-color: #2563eb;
            }}
            .footer {{
                background-color: #f9fafb;
                padding: 30px;
                text-align: center;
                border-top: 1px solid #e5e7eb;
                font-size: 12px;
                color: #999;
            }}
            .footer p {{
                margin-bottom: 10px;
            }}
            .footer a {{
                color: #ef4444;
                text-decoration: none;
            }}
            .divider {{
                height: 1px;
                background-color: #e5e7eb;
                margin: 30px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="email-wrapper">
                <div class="header">
                    <h1>Payout Rejected</h1>
                    <p>Your withdrawal request could not be processed</p>
                </div>

                <div class="content">
                    <div class="greeting">Hi {seller_name},</div>

                    <div class="message">
                        We've reviewed your payout request and unfortunately it was rejected.
                        This may be due to verification requirements or account issues. Please contact our support team for more information.
                    </div>

                    <div class="alert-box">
                        <h2>Rejection Details</h2>
                        <p>
                            Your payout request for €{amount:.2f} has been rejected. Your balance remains in your account
                            and you can submit a new request after addressing the issue.
                        </p>
                    </div>

                    <div class="details-box">
                        <div class="details-row">
                            <span class="details-label">Status:</span>
                            <span class="details-value" style="color: #dc2626;">Rejected</span>
                        </div>
                        <div class="details-row">
                            <span class="details-label">Amount:</span>
                            <span class="details-value">€{amount:.2f}</span>
                        </div>
                        <div class="details-row">
                            <span class="details-label">Refunded To:</span>
                            <span class="details-value">Your Account Balance</span>
                        </div>
                    </div>

                    <div class="next-steps">
                        <h3>What Should You Do?</h3>
                        <p>
                            1. Check your bank account details are correct<br>
                            2. Verify your account information<br>
                            3. Ensure you meet our seller requirements<br>
                            4. Contact support if you need assistance<br>
                            5. Submit a new withdrawal request once issues are resolved
                        </p>
                    </div>

                    <div class="divider"></div>

                    <a href="https://reelzila.studio/contact" class="cta-button">Contact Support</a>
                </div>

                <div class="footer">
                    <p>© 2024 Reelzila. All rights reserved.</p>
                    <p>
                        <a href="https://reelzila.studio/privacy">Privacy Policy</a> |
                        <a href="https://reelzila.studio/terms">Terms of Service</a> |
                        <a href="https://reelzila.studio/contact">Support</a>
                    </p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


def get_admin_payout_ready_email(seller_name: str, amount: float, paypal_email: str, seller_id: str) -> str:
    """Email template for admin notification that payout is ready to transfer"""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Payout Ready for Transfer</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f9fafb;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .email-wrapper {{
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                color: white;
                padding: 40px 20px;
                text-align: center;
            }}
            .header h1 {{
                font-size: 28px;
                margin-bottom: 10px;
                font-weight: 600;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .message {{
                font-size: 15px;
                line-height: 1.8;
                color: #555;
                margin-bottom: 30px;
            }}
            .action-box {{
                background-color: #fef3c7;
                border: 2px solid #f59e0b;
                padding: 25px;
                margin: 30px 0;
                border-radius: 8px;
            }}
            .action-box h2 {{
                color: #92400e;
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 15px;
            }}
            .details {{
                background-color: #f3f4f6;
                padding: 20px;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .detail-row {{
                display: flex;
                justify-content: space-between;
                padding: 12px 0;
                font-size: 14px;
                border-bottom: 1px solid #e5e7eb;
            }}
            .detail-row:last-child {{
                border-bottom: none;
            }}
            .detail-label {{
                color: #666;
                font-weight: 500;
            }}
            .detail-value {{
                color: #333;
                font-weight: 600;
                word-break: break-all;
            }}
            .amount {{
                font-size: 24px;
                color: #f59e0b;
                font-weight: 700;
                margin: 15px 0;
            }}
            .cta-button {{
                display: inline-block;
                background-color: #f59e0b;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 4px;
                font-weight: 600;
                margin-top: 20px;
                font-size: 14px;
            }}
            .cta-button:hover {{
                background-color: #d97706;
            }}
            .footer {{
                background-color: #f9fafb;
                padding: 30px;
                text-align: center;
                border-top: 1px solid #e5e7eb;
                font-size: 12px;
                color: #999;
            }}
            .footer p {{
                margin-bottom: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="email-wrapper">
                <div class="header">
                    <h1>✓ Payout Approved</h1>
                    <p>Ready for PayPal transfer</p>
                </div>

                <div class="content">
                    <div class="message">
                        A payout has been approved and is now ready for PayPal transfer.
                        Please process the transfer and mark as completed in the admin dashboard.
                    </div>

                    <div class="action-box">
                        <h2>Action Required: Transfer to PayPal</h2>
                        <div class="amount">€{amount:.2f}</div>
                        <p style="font-size: 14px; color: #92400e; margin-top: 10px;">
                            Send this amount to the PayPal email below, then mark as completed in the admin dashboard.
                        </p>
                    </div>

                    <div class="details">
                        <div class="detail-row">
                            <span class="detail-label">Seller Name:</span>
                            <span class="detail-value">{seller_name}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">PayPal Email:</span>
                            <span class="detail-value">{paypal_email}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Amount:</span>
                            <span class="detail-value">€{amount:.2f}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Seller ID:</span>
                            <span class="detail-value">{seller_id}</span>
                        </div>
                    </div>

                    <div class="message" style="background-color: #f0f9ff; padding: 15px; border-radius: 4px; border-left: 4px solid #3b82f6;">
                        <strong>Steps:</strong><br>
                        1. Log into PayPal business account<br>
                        2. Send €{amount:.2f} to {paypal_email}<br>
                        3. Return to admin dashboard<br>
                        4. Click "Mark Completed" for this payout<br>
                        5. Seller will receive completion email
                    </div>

                    <a href="https://youradmin.com/payouts" class="cta-button">Go to Payouts Dashboard</a>
                </div>

                <div class="footer">
                    <p>© 2024 AI Video Generator Admin Panel</p>
                    <p>This is an automated message - do not reply to this email</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


# Function to select and render appropriate template
def get_payout_email(status: str, seller_name: str, amount: float, account_holder: str = "", seller_id: str = "") -> str:
    """Get email template based on payout status"""
    if status.lower() == "approved":
        return get_payout_approved_email(seller_name, amount, account_holder)
    elif status.lower() == "completed":
        return get_payout_completed_email(seller_name, amount)
    elif status.lower() == "rejected":
        return get_payout_rejected_email(seller_name, amount)
    else:
        # Default to approved template
        return get_payout_approved_email(seller_name, amount, account_holder)


def get_admin_email(seller_name: str, amount: float, paypal_email: str, seller_id: str) -> str:
    """Get admin notification email"""
    return get_admin_payout_ready_email(seller_name, amount, paypal_email, seller_id)


def get_new_withdrawal_request_email(seller_name: str, seller_email: str, amount: float, seller_id: str, request_id: str, bank_details: dict = None) -> str:
    """Email template for admin notification of NEW withdrawal request (before approval)"""
    # Format bank details for display
    if bank_details:
        iban = bank_details.get('iban', 'Not provided')
        account_holder = bank_details.get('accountHolder', 'Not provided')
        bank_name = bank_details.get('bankName', 'Not specified')
        bic = bank_details.get('bic', 'Not specified')
    else:
        iban = 'Not provided'
        account_holder = 'Not provided'
        bank_name = 'Not specified'
        bic = 'Not specified'
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>New Withdrawal Request</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                background-color: #f9fafb;
            }}
            .container {{
                max-width: 650px;
                margin: 0 auto;
                padding: 20px;
            }}
            .email-wrapper {{
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                color: white;
                padding: 40px 20px;
                text-align: center;
            }}
            .header h1 {{
                font-size: 28px;
                margin-bottom: 10px;
                font-weight: 600;
            }}
            .header p {{
                font-size: 16px;
                opacity: 0.9;
            }}
            .content {{
                padding: 40px 30px;
            }}
            .alert-box {{
                background-color: #dbeafe;
                border-left: 4px solid #3b82f6;
                padding: 20px;
                margin: 20px 0;
                border-radius: 4px;
            }}
            .alert-box h2 {{
                color: #1e40af;
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 10px;
            }}
            .alert-box p {{
                color: #1e3a8a;
                font-size: 14px;
            }}
            .details {{
                background-color: #f9fafb;
                padding: 25px;
                border-radius: 8px;
                margin: 30px 0;
                border: 1px solid #e5e7eb;
            }}
            .details-title {{
                font-size: 14px;
                text-transform: uppercase;
                color: #6b7280;
                font-weight: 600;
                margin-bottom: 20px;
                letter-spacing: 0.5px;
            }}
            .detail-row {{
                display: flex;
                justify-content: space-between;
                padding: 15px 0;
                font-size: 14px;
                border-bottom: 1px solid #e5e7eb;
            }}
            .detail-row:last-child {{
                border-bottom: none;
            }}
            .detail-label {{
                color: #6b7280;
                font-weight: 500;
                min-width: 140px;
            }}
            .detail-value {{
                color: #111827;
                font-weight: 600;
                word-break: break-all;
                text-align: right;
                flex: 1;
            }}
            .amount {{
                font-size: 32px;
                color: #3b82f6;
                font-weight: 700;
                margin: 20px 0;
                text-align: center;
            }}
            .action-section {{
                background-color: #fef3c7;
                border: 2px solid #fbbf24;
                padding: 25px;
                margin: 30px 0;
                border-radius: 8px;
            }}
            .action-section h3 {{
                color: #92400e;
                font-size: 16px;
                font-weight: 600;
                margin-bottom: 15px;
            }}
            .action-section ol {{
                margin-left: 20px;
                color: #92400e;
            }}
            .action-section li {{
                margin-bottom: 10px;
                font-size: 14px;
                line-height: 1.6;
            }}
            .copy-box {{
                background-color: #f3f4f6;
                padding: 12px 15px;
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 14px;
                margin: 10px 0;
                border: 1px solid #d1d5db;
                word-break: break-all;
            }}
            .footer {{
                background-color: #f9fafb;
                padding: 30px;
                text-align: center;
                border-top: 1px solid #e5e7eb;
                font-size: 12px;
                color: #9ca3af;
            }}
            .footer p {{
                margin-bottom: 10px;
            }}
            .timestamp {{
                color: #6b7280;
                font-size: 13px;
                margin-top: 20px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="email-wrapper">
                <div class="header">
                    <h1>💰 New Withdrawal Request</h1>
                    <p>Action Required - Seller Payout</p>
                </div>

                <div class="content">
                    <div class="alert-box">
                        <h2>🔔 New Payout Request Submitted</h2>
                        <p>A seller has requested a withdrawal. Please process this bank transfer from the admin dashboard.</p>
                    </div>

                    <div class="amount">€{amount:.2f}</div>

                    <div class="details">
                        <div class="details-title">📋 Withdrawal Request Details</div>

                        <div class="detail-row">
                            <span class="detail-label">Request ID:</span>
                            <span class="detail-value">{request_id}</span>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">Seller Name:</span>
                            <span class="detail-value">{seller_name}</span>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">Seller ID:</span>
                            <span class="detail-value">{seller_id}</span>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">Seller Email:</span>
                            <span class="detail-value">{seller_email}</span>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">Account Holder:</span>
                            <span class="detail-value" style="color: #3b82f6;">{account_holder}</span>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">IBAN:</span>
                            <span class="detail-value" style="font-family: monospace;">{iban}</span>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">Bank Name:</span>
                            <span class="detail-value">{bank_name}</span>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">BIC/SWIFT:</span>
                            <span class="detail-value" style="font-family: monospace;">{bic}</span>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">Amount:</span>
                            <span class="detail-value" style="color: #059669;">€{amount:.2f}</span>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">Status:</span>
                            <span class="detail-value" style="color: #f59e0b;">Pending</span>
                        </div>
                    </div>

                    <div class="action-section">
                        <h3>⚙️ Processing Steps:</h3>
                        <ol>
                            <li><strong>Review the request</strong> in the admin dashboard at reelzila-admin.vercel.app/payouts</li>
                            <li><strong>Approve the request</strong> if details are correct</li>
                            <li><strong>Initiate bank transfer</strong> to:<br>
                                <div class="copy-box">IBAN: {iban}<br>Account Holder: {account_holder}</div>
                            </li>
                            <li><strong>Amount to send:</strong><br>
                                <div class="copy-box">€{amount:.2f}</div>
                            </li>
                            <li><strong>Reference:</strong> "Reelzila Payout - #{request_id}"</li>
                            <li><strong>After transfer is complete:</strong> Mark as "Completed" in the admin dashboard</li>
                        </ol>
                    </div>

                    <div class="timestamp">
                        Request received at: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
                    </div>
                </div>

                <div class="footer">
                    <p><strong>reelzila</strong> - AI Video Generation Platform</p>
                    <p>This is an automated notification. Do not reply to this email.</p>
                    <p>If you have questions, please contact your technical support team.</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
