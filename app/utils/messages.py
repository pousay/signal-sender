"""Centralized Persian message templates and constants."""


class Messages:
    """Persian user-facing copy and button labels."""

    # Button Labels
    BTN_POST_SIGNAL = "📨 ارسال پست"
    BTN_UPDATE_PHOTOS = "🖼 بروزرسانی عکس‌ها"
    BTN_SEND_PREMIUM = "⭐ ارسال اشتراک ویژه"
    BTN_CANCEL = "❌ لغو"
    BTN_APPROVE_AND_PUBLISH = "✅ تأیید و انتشار"
    BTN_RETRY_PUBLISH = "🔄 تلاش مجدد"
    BTN_VIEW_POSITION = "📝 برای مشاهده مشخصات پـوزیشن کلیک کنید"
    BTN_VIEW_LINK = "مشاهده"

    # Start and Welcome Messages
    ADMIN_WELCOME = (
        "سلام مدیر گرامی 🌹\n"
        "به پنل مدیریت ربات سیگنال خوش آمدید.\n\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب نمایید:"
    )

    USER_WELCOME = (
        "سلام و درود! 🌹\n\n"
        "به ربات سیگنال‌های تحلیلی خوش آمدید.\n"
        "سیگنال‌های عمومی در کانال منتشر می‌شوند. برای مشاهده کامل جزئیات پوزیشن‌ها "
        "(حد فروش، حد ضرر و اهداف) نیاز به داشتن اشتراک ویژه دارید.\n\n"
        "برای تهیه اشتراک ویژه با پشتیبانی در ارتباط باشید:\n"
        "🆔 : {support_link}"
    )

    UNAUTHORIZED = "⛔ شما اجازه دسترسی به این بخش را ندارید."
    PRIVATE_ONLY = "⚠️ این دستور تنها در گفتگوی خصوصی با ربات قابل استفاده است."

    # Workflow Cancellation
    OPERATION_CANCELLED = "عملیات با موفقیت لغو شد. ❌"

    # Signal Workflow Messages
    PROMPT_SIGNAL_TEXT = "لطفاً متن سیگنال را ارسال یا پیست نمایید:\n\n"
    SIGNAL_PARSE_ERROR = (
        "❌ خطا در پردازش سیگنال!\n"
        "مقدار «Sell limit» در متن ارسالی یافت نشد یا مقدار آن نامعتبر است.\n"
        "لطفاً متن سیگنال را اصلاح نموده و مجدداً ارسال کنید."
    )
    CAPTION_TOO_LONG = (
        "❌ متن سیگنال طولانی‌تر از حد مجاز کپشن تلگرام است (حداکثر ۱۰۲۴ کاراکتر)."
    )
    NO_PHOTOS_AVAILABLE = (
        "❌ هیچ عکسی در پایگاه داده ذخیره نشده است!\n"
        "لطفاً ابتدا از طریق دکمه «🖼 بروزرسانی عکس‌ها» تصاویر کانال مرجع را همگام‌سازی نمایید."
    )
    PREVIEW_TITLE = "📋 **پیش‌نمایش پست سیگنال:**\n\nجهت انتشار در کانال تأیید نمایید:"
    PUBLISH_SUCCESS = (
        "✅ پست سیگنال با موفقیت در کانال منتشر شد.\nشناسه پیام: {message_id}"
    )
    PUBLISH_FAILED = "❌ خطا در انتشار پست در کانال: {error}"
    PUBLISH_ALREADY_DONE = "⚠️ این سیگنال پیش‌تر منتشر شده است."

    # Photo Synchronization Messages
    PHOTO_SYNC_STARTING = (
        "⏳ در حال همگام‌سازی تصاویر از کانال مرجع... لطفاً شکیبا باشید."
    )
    PHOTO_SYNC_SUCCESS = (
        "✅ همگام‌سازی تصاویر با موفقیت انجام شد.\n"
        "تعداد عکس‌های ذخیره‌شده: {count} عدد"
    )
    PHOTO_SYNC_ZERO = (
        "⚠️ همگام‌سازی به پایان رسید اما هیچ عکسی در کانال مرجع یافت نشد.\n"
        "امکان ارسال سیگنال تا زمان وجود عکس در کانال مرجع وجود ندارد."
    )
    PHOTO_SYNC_FAILED = (
        "❌ خطا در همگام‌سازی تصاویر از کانال مرجع: {error}\n"
        "مجموعه تصاویر قبلی دست‌نخورده باقی ماند."
    )
    PHOTO_SYNC_BOT_RESTRICTION = (
        "تلگرام اجازه خواندن تاریخچه را به توکن ربات نمی‌دهد.\n"
        "برای حل این مورد:\n"
        "۱. ربات را به عنوان Admin با دسترسی خواندن پیام‌ها به کانال مرجع اضافه نمایید.\n"
        "۲. یا متغیر USER_SESSION_STRING را در فایل .env تنظیم کنید.\n"
        "(با اجرای scripts/generate_session.py)"
    )
    PHOTO_SYNC_NO_ACCESS = (
        "ربات به کانال مرجع دسترسی ندارد.\n"
        "لطفاً اطمینان حاصل کنید ربات به عنوان Admin در کانال مرجع عضو است "
        "یا USER_SESSION_STRING در .env تنظیم شده است."
    )

    # Subscription Workflow Messages
    PROMPT_USER_ID = "لطفاً **شناسه عددی (Numeric User ID)** کاربر را ارسال نمایید:"
    INVALID_USER_ID = (
        "❌ شناسه کاربر نامعتبر است! لطفاً فقط یک عدد صحیح مثبت ارسال کنید:"
    )
    PROMPT_DURATION_DAYS = (
        "لطفاً مدت زمان اشتراک را به **تعداد روز** وارد نمایید (مثال: 30):"
    )
    INVALID_DURATION_DAYS = (
        "❌ تعداد روز نامعتبر است! لطفاً یک عدد صحیح بین ۱ تا {max_days} وارد کنید:"
    )

    SUBSCRIPTION_CONFIRM_ADMIN = (
        "✅ اشتراک ویژه کاربر `{user_id}` با موفقیت ثبت شد.\n"
        "مدت: {days} روز\n"
        "تاریخ انقضا: {expires_at} UTC"
    )
    SUBSCRIPTION_USER_NOT_STARTED = (
        "⚠️ اشتراک در سیستم ثبت شد، اما پیام فعال‌سازی برای کاربر ارسال نشد "
        "(احتمالاً کاربر هنوز ربات را استارت نکرده است یا ربات را بلاک کرده است)."
    )

    # User Subscription Messages (Exact required text)
    SUBSCRIPTION_ACTIVATED_USER = (
        "اشتراک شما با موفقیت فعال شد.✅\n\n" "از همراهی شما سپاسگزاریم.🌹"
    )

    SUBSCRIPTION_EXPIRED_USER = (
        "اشتراک شما به پایان رسید.\n\n" "از همراهی شما سپاسگزاریم.🌹"
    )

    SUBSCRIPTION_REMINDER_24H = (
        "⏳ یادآوری: اشتراک ویژه شما ظرف ۲۴ ساعت آینده به پایان می‌رسد.\n"
        "جهت تمدید به پشتیبانی پیام دهید:\n"
        "🆔 : {support_link}"
    )

    # Signal Access Messages
    SIGNAL_NOT_FOUND = "❌ سیگنال مورد نظر یافت نشد یا منقضی شده است."
    NON_PREMIUM_MESSAGE = (
        "⚠️ برای مشاهده مشخصات پوزیشن،\n"
        "جهت تهیه اشتراک به ادمین کانال پیام دهید:\n\n"
        "🆔 : {support_username}"
    )

    # Backup Messages
    BACKUP_CREATING = "⏳ در حال آماده‌سازی فایل پشتیبان..."
    BACKUP_SUCCESS = "✅ فایل پشتیبان پایگاه داده با موفقیت ایجاد شد."
    BACKUP_FAILED = "❌ خطا در ایجاد فایل پشتیبان: {error}"

    # General Error
    UNEXPECTED_ERROR = "❌ خطایی در پردازش رخ داده است. لطفاً بعداً تلاش فرمایید."
