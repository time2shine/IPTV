def scrape_dw(channel_id, display_name, logo_url, url):
    logging.info(f"Fetching DW English schedule from {display_name} ...")
    programmes = []

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        # ✅ Current Bangladesh time
        now = datetime.now(timezone.utc) + timedelta(hours=6)

        # ✅ Extract current program
        current_tag = soup.find("h2", attrs={"aria-label": True})
        current_title = current_tag.get_text(strip=True) if current_tag else None

        # ✅ Extract upcoming schedule rows
        schedule_rows = soup.find_all("div", attrs={"role": "row"})

        parsed_schedule = []
        for row in schedule_rows:
            time_tag = row.find("span", attrs={"role": "cell", "class": lambda c: c and "time" in c})
            program_names = row.find("div", attrs={"role": "cell", "class": lambda c: c and "program-names" in c})

            if time_tag and program_names:
                time_text = time_tag.get_text(strip=True)  # e.g., "20:34"
                names = program_names.find_all("span")
                main_title = names[0].get_text(strip=True) if len(names) > 0 else ""

                try:
                    start_time = datetime.strptime(time_text, "%H:%M")
                    start_dt = now.replace(hour=start_time.hour, minute=start_time.minute, second=0, microsecond=0)
                    if start_dt < now:
                        start_dt += timedelta(days=1)
                except:
                    continue

                parsed_schedule.append({"title": main_title, "start": start_dt})

        # ✅ Assign stop times based on next start or +1 min for last
        for i, prog in enumerate(parsed_schedule):
            start_dt = prog["start"]
            stop_dt = parsed_schedule[i + 1]["start"] if i + 1 < len(parsed_schedule) else start_dt + timedelta(minutes=1)
            programmes.append({
                "title": prog["title"],
                "start": start_dt,
                "stop": stop_dt
            })

        # ✅ If current program is missing, add it as previous slot
        if current_title and programmes:
            first_start = programmes[0]["start"]
            current_start = first_start - timedelta(minutes=30)
            programmes.insert(0, {
                "title": current_title,
                "start": current_start,
                "stop": first_start
            })

        logging.info(f"Fetched {len(programmes)} programmes for {display_name}")

    except Exception as e:
        logging.error(f"Failed to fetch DW English: {e}")

    return {"id": channel_id, "name": display_name, "logo": logo_url, "programmes": programmes}
