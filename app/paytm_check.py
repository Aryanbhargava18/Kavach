"""`make paytm-check ORDER=<order id>`: one live call to Paytm's Transaction Status API with the keys in .env."""
import asyncio
import json
import sys

from . import paytm_live


def main() -> None:
    if not paytm_live.configured():
        sys.exit("Set PAYTM_MID and PAYTM_MERCHANT_KEY in .env (Paytm dashboard > Developer settings, test mode).")
    if len(sys.argv) < 2:
        sys.exit("usage: python -m app.paytm_check <order id>")
    r = asyncio.run(paytm_live.order_status(sys.argv[1]))
    print(json.dumps(r, indent=1))
    print("\nOK: Paytm answered." if r.get("result_code") else "\nPaytm answered, but without a result code. Check the MID/key/environment.")


if __name__ == "__main__":
    main()
