CREATE TABLE "orders" (
	"id" text PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"symbol" varchar(10) NOT NULL,
	"type" "order_type" NOT NULL,
	"quantity" numeric(18, 8) NOT NULL,
	"price" numeric(18, 8) NOT NULL,
	"stop_loss" numeric(18, 8),
	"take_profit" numeric(18, 8),
	"status" "order_status" DEFAULT 'PENDING' NOT NULL,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "positions" (
	"id" text PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"symbol" varchar(10) NOT NULL,
	"quantity" numeric(18, 8) NOT NULL,
	"entry_price" numeric(18, 8) NOT NULL,
	"current_price" numeric(18, 8) NOT NULL,
	"pnl" numeric(18, 2) DEFAULT '0' NOT NULL,
	"pnl_percent" numeric(5, 2) DEFAULT '0' NOT NULL,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now()
);
--> statement-breakpoint
CREATE TABLE "users" (
	"id" text PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"email" varchar(255) NOT NULL,
	"name" varchar(255),
	"balance" numeric(18, 2) DEFAULT '50000' NOT NULL,
	"equity" numeric(18, 2) DEFAULT '50000' NOT NULL,
	"margin_level" numeric(5, 2) DEFAULT '0' NOT NULL,
	"created_at" timestamp DEFAULT now(),
	"updated_at" timestamp DEFAULT now(),
	CONSTRAINT "users_email_unique" UNIQUE("email")
);
