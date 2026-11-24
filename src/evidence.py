import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tools_gw as tools

LOW, HIGH = 0.85, 1.15
GAP_SHARE = 0.25

CONTEXT_TOOLS = ["get_weather", "get_calendar", "get_earthquakes"]


def context_plan(cmp_):
    """Asama 2 (hava, takvim, deprem) gerekli mi? Yalniz karsilastirma ciktisina bakar; esikler judge ile ayni."""
    total, missing = cmp_.get("hours_in_window", 0), cmp_.get("hours_missing", 0)
    ratio = cmp_.get("median_ratio_excl_etl_flagged")
    if ratio is None:
        ratio = cmp_.get("median_ratio_all")
    if total > 0 and missing == total:
        return {"gerekli": False, "neden": "pencerenin tum saatleri eksik, olculecek trafik yok"}
    if ratio is None:
        return {"gerekli": False, "neden": "karşılaştırma için yeterli geçmiş veri yok, sapma ölçülemedi"}
    if ratio < LOW or ratio > HIGH:
        return {"gerekli": True, "neden": f"sapma var (normale göre oran {ratio}), olası nedenler araştırılır"}
    return {"gerekli": False, "neden": f"belirgin sapma yok (normale göre oran {ratio})"}


def _judge_core(s, e):
    etl = tools.check_etl_log(s, e)
    cmp_ = tools.compare_same_weekday_history(s, e)
    plan = context_plan(cmp_)
    if plan["gerekli"]:
        wx = tools.get_weather(s, e)
        cal = tools.get_calendar(s, e)
        eq = tools.get_earthquakes(s, e)
    else:
        wx, cal, eq = {}, {"days": []}, {"n_relevant": 0}

    flagged = cmp_.get("hours_etl_flagged", 0)
    gaps = sum(
        1 for g in etl.get("gaps_near_window", [])
        if g.get("overlaps_window")
    )

    n_clean = cmp_.get("n_clean_hours", 0)
    clean_ratio = cmp_.get("median_ratio_excl_etl_flagged")
    ratio = clean_ratio

    if ratio is None:
        ratio = cmp_.get("median_ratio_all")

    deviation = (
        ratio is not None and
        (ratio < LOW or ratio > HIGH)
    )

    holidays = sorted({
        d["holiday"]
        for d in cal.get("days", [])
        if d.get("holiday")
    })

    precip = wx.get("precip_total_mm", 0)
    precip_day = wx.get("precip_max_day_mm", precip)
    p90 = wx.get("period_daily_precip_p90_mm", 1e9)
    wind = wx.get("wind_max_kmh", 0)

    weather_extreme = precip_day > p90 or wind > 40

    hypotheses = {
        k: "desteklemiyor"
        for k in [
            "veri_hatasi",
            "hava",
            "tatil",
            "deprem",
            "aciklanamayan"
        ]
    }

    notes = []

    if "error" in wx:
        hypotheses["hava"] = "belirsiz"
        notes.append("Hava verisi bu dönem için yok")

    etl_missing = "error" in etl
    if etl_missing:
        notes.append("ETL logu bu dönem için yok: veri kalitesi doğrulanamadı")

    if deviation:

        if flagged or gaps:
            partial = (
                n_clean > 0 and
                clean_ratio is not None
            )

            if not partial:
                hypotheses["veri_hatasi"] = "destekliyor"

            notes.append(
                f"ETL işaretli saat={flagged}, "
                f"kesişen boşluk={gaps}, "
                f"temiz saat={n_clean}"
            )

        if holidays:
            hypotheses["tatil"] = "destekliyor"
            notes.append("Tatil: " + ", ".join(holidays))
        ctx_half, ctx_admin, ctx_school = [], [], []
        for d_ in cal.get("days", []):
            if d_.get("half_day"):
                ctx_half.append(d_["date"] + " " + d_["half_day"] + " (yar\u0131m g\u00fcn)")
            if d_.get("admin_leave"):
                ctx_admin.append(d_["date"])
            if d_.get("school") == "tatil":
                nm_ = (d_.get("school_note") or "").split(" | ")[0]
                if nm_ and nm_ not in ctx_school:
                    ctx_school.append(nm_)
        half_dates = {c_[:10] for c_ in ctx_half}
        admin_full = [x_ for x_ in ctx_admin if x_ not in half_dates]
        admin_rule = bool(admin_full) and hypotheses["tatil"] == "desteklemiyor"
        if admin_rule:
            hypotheses["tatil"] = "belirsiz"
            notes.append("Tatil: resm\u00ee tatil yok; kamu idari izni var (yaln\u0131z devlet memurlar\u0131 i\u00e7in, etkisi k\u0131smi olabilir): " + ", ".join(admin_full))
            ctx_admin = [x_ for x_ in ctx_admin if x_ not in admin_full]
        ctx_bits = list(ctx_half)
        if ctx_admin:
            ctx_bits.append("idari izin (kamu): " + ", ".join(ctx_admin))
        if ctx_school:
            ctx_bits.append("okul tatili: " + ", ".join(ctx_school))
        if ctx_bits:
            notes.append("Takvim ba\u011flam\u0131 (kan\u0131t, karar kural\u0131na girmez): " + "; ".join(ctx_bits))

        if weather_extreme:
            hypotheses["hava"] = "destekliyor"
            notes.append(
                f"Aşırı hava: yağış={precip} mm"
                + (f" (en yağışlı gün {precip_day} mm)" if precip_day != precip else "")
                + ", "
                f"rüzgâr={wind} km/sa"
            )

        if "error" in eq:
            hypotheses["deprem"] = "belirsiz"
            notes.append("Deprem kataloğu dönemi kapsamıyor")

        elif eq.get("n_relevant", 0) > 0:
            hypotheses["deprem"] = "belirsiz"
            notes.append(
                f"İlgili deprem sayısı: {eq['n_relevant']}"
            )

        other_supported = any(
            hypotheses[k] != "desteklemiyor"
            for k in [
                "veri_hatasi",
                "hava",
                "tatil",
                "deprem"
            ]
        )

        if not other_supported:
            hypotheses["aciklanamayan"] = "destekliyor"
            notes.append("Sapmayı açıklayan neden bulunamadı")

    else:
        notes.append("Belirgin trafik sapması yok")

        if weather_extreme:
            notes.append("Aşırı hava var ancak trafik sapması yok")

        if "error" not in eq and eq.get("n_relevant", 0) > 0:
            notes.append("Deprem kaydı var ancak trafik sapması yok")

    if not deviation:
        confidence = "orta"
        needs_human = False

    elif (
        hypotheses["aciklanamayan"] == "destekliyor"
        or "belirsiz" in hypotheses.values()
    ):
        confidence = "dusuk"
        needs_human = True

    else:
        confidence = "orta"
        needs_human = False

    if etl_missing and deviation:
        confidence = "dusuk"
        needs_human = True

    return {
        "pencere": f"{s} - {e}",
        "etl_log_yok": etl_missing,
        "arac_plani": plan,
        "medyan_oran": ratio,
        "sapma_var": deviation,
        "hipotezler": hypotheses,
        "notlar": notes,
        "guven": confidence,
        "needs_human": needs_human
    }

def judge(s, e):
    r = _judge_core(s, e)
    cmp_ = tools.compare_same_weekday_history(s, e)
    total = cmp_.get("hours_in_window", 0)
    missing = cmp_.get("hours_missing", 0)
    r["saat_toplam"] = total
    r["saat_eksik"] = missing
    r["veri_yok"] = False
    r["degerlendirilemedi"] = False
    if total > 0 and missing == total:
        r["veri_yok"] = True
        r["sapma_var"] = True
        r["hipotezler"] = {k: "desteklemiyor" for k in r["hipotezler"]}
        r["hipotezler"]["veri_hatasi"] = "destekliyor"
        r["notlar"] = ["pencerenin tüm saatleri kaynak dosyada yok"]
        r["guven"] = "orta"
        r["needs_human"] = False
    elif r["medyan_oran"] is None:
        r["degerlendirilemedi"] = True
        r["guven"] = "dusuk"
        r["needs_human"] = True
        r["hipotezler"] = {k: "belirsiz" for k in r["hipotezler"]}
        r["notlar"] = ["karşılaştırma için yeterli geçmiş veri yok (en az 3 geçerli hafta gerekir); nedenler değerlendirilemedi"]
    elif missing > 0:
        r["notlar"].append(f"pencerede {missing}/{total} saat kaynak dosyada yok")
    flagged = cmp_.get("hours_etl_flagged", 0)
    r["veri_kalitesi_uyarisi"] = None
    if flagged > 0 or missing > 0 or r.get("etl_log_yok"):
        oran = round(missing / total, 2) if total else 0.0
        r["veri_kalitesi_uyarisi"] = {"isaretli_saat": flagged, "eksik_saat": missing,
                                      "toplam_saat": total, "eksik_oran": oran}
        if r.get("etl_log_yok"):
            r["veri_kalitesi_uyarisi"]["etl_log_yok"] = True
        if (not r["degerlendirilemedi"]) and total > 0 and oran >= GAP_SHARE \
                and r["hipotezler"]["veri_hatasi"] != "destekliyor":
            r["hipotezler"]["veri_hatasi"] = "destekliyor"
            r["hipotezler"]["aciklanamayan"] = "desteklemiyor"
            r["notlar"].append(f"eksik saat oranı {oran} >= {GAP_SHARE}: veri hatası")
            if r["sapma_var"]:
                belirsiz = "belirsiz" in r["hipotezler"].values()
                r["guven"] = "dusuk" if belirsiz else "orta"
                r["needs_human"] = belirsiz
    # v4 (olculmemis): ETL'de isaretli saat payi esigi asiyor, eksik saat yok, temiz saatlerde sapma yok
    if (not r["veri_yok"]) and (not r["degerlendirilemedi"]) and total > 0 and (not r["sapma_var"]) \
            and round(flagged / total, 2) >= GAP_SHARE and round(missing / total, 2) < GAP_SHARE:
        r["hipotezler"]["veri_hatasi"] = "destekliyor"
        r["hipotezler"]["aciklanamayan"] = "desteklemiyor"
        r["notlar"].append(f"Veri yükleme kaydında (ETL) işaretli saat oranı {round(flagged / total, 2)} >= {GAP_SHARE}: "
                           "veri sorunu olmayan saatlerdeki 'sapma yok' sonucu günün tamamı için geçerli sayılmaz, veri hatası")
    r["karisik_durum"] = False
    if (not r["veri_yok"]) and (not r["degerlendirilemedi"]) and total > 0 \
            and round(missing / total, 2) >= GAP_SHARE and r["sapma_var"]:
        r["karisik_durum"] = True
        r["guven"] = "dusuk"
        r["needs_human"] = True
        r["notlar"].append(f"eksik veri ({missing}/{total} saat) ve veri sorunu olmayan saatlerde sapma (oran {r['medyan_oran']}) birlikte: "
                           "gerçek trafik değişimi dışlanamaz, ek inceleme gerekli")
    # Bilgi amacli: gun duzeyi medyan yerel etkileri seyreltir; saatlik sayilar karar kuralini DEGISTIRMEZ.
    r["saatlik_bilgi"] = {"temiz_saat": cmp_.get("n_clean_hours"),
                          "baseline_alti_0.7": cmp_.get("n_clean_below_0.7"),
                          "baseline_ustu_1.3": cmp_.get("n_clean_above_1.3")}
    return r
